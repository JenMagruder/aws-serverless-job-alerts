import json
import boto3
import os
import hashlib
from datetime import datetime, timedelta
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

JOBS_TABLE = os.environ['JOBS_TABLE_NAME']
SEEN_TABLE = os.environ['SEEN_TABLE_NAME']
SNS_TOPIC = os.environ['SNS_TOPIC_ARN']
MIN_SALARY = int(os.environ.get('MIN_SALARY', 'input')) #or comment out

# Add job titles you are looking for
REQUIRED_KEYWORDS = [
    'cloud engineer', 'devops engineer', 'aws cloud engineer',
    'junior cloud', 'associate cloud', 'junior devops', 'associate devops',
    'cloud support', 'technical support engineer',
    'cloud computing', 'cloud aws'
]

# Add clearance types to exclude, e.g. 'top secret', 'ts/sci', 'polygraph'
# If you don't need clearance filtering, delete this section and the clearance check in filter_job
EXCLUDE_CLEARANCE = [
    ''
]

# Add keywords to exclude from job titles, e.g. 'senior', 'architect', 'manager'
EXCLUDE_KEYWORDS = [
    'intern', 'internship'
]

# Add locations to exclude, e.g. 'maryland', 'baltimore'
EXCLUDE_LOCATIONS = [
    ''
]

# Add acceptable commute areas, e.g. 'your-city', 'nearby-city'
ACCEPTABLE_AREAS = [
    'remote'
]

# Add or remove legitimate job platforms
LEGITIMATE_ATS = [
    'indeed.com', 'workday.com', 'greenhouse.io', 'lever.co',
    'taleo.net', 'careers.', 'jobs.', 'usajobs.gov', 'linkedin.com'
]

# Add platforms to block, e.g. aggregators or sites requiring login
BLOCKED_PLATFORMS = [
    'clearancejobs.com',
    'dice.com',
    'monster.com'
]

def fetch_jobs_from_indeed():
    import requests
    
    SERPAPI_KEY = os.environ.get('SERPAPI_KEY')
    
    # Add job titles to search for
    searches = [
        'cloud engineer',
        'devops engineer',
        'aws cloud engineer'
    ]
    
    all_jobs = []
    
    for search_term in searches:
        print(f"Searching Google Jobs via SerpAPI: {search_term}")
        
        params = {
            'engine': 'google_jobs',
            'q': search_term,
            'location': 'Your State, United States',  # Update with your location
            'api_key': SERPAPI_KEY
        }
        
        try:
            response = requests.get('https://serpapi.com/search', params=params)
            print(f"SerpAPI Status Code: {response.status_code}") 
            
            data = response.json()
            
            jobs = data.get('jobs_results', [])
            print(f"Found {len(jobs)} jobs for {search_term}")
            
            for job in jobs:
                apply_options = job.get('apply_options', [])
                apply_link = apply_options[0].get('link', '') if apply_options else job.get('share_link', '')
                
                job_id = hashlib.md5(str(apply_link).encode()).hexdigest()
                
                all_jobs.append({
                    'job_id': job_id,
                    'source': 'google_jobs',
                    'title': job.get('title', ''),
                    'company': {'display_name': job.get('company_name', '')},
                    'location': {'display_name': job.get('location', '')},
                    'description': job.get('description', ''),
                    'redirect_url': apply_link,
                    'created': job.get('detected_extensions', {}).get('posted_at', '')
                })
        except Exception as e:
            print(f"Error with SerpAPI for {search_term}: {e}")
            import traceback
            traceback.print_exc()
    
    # Dedupe
    seen_ids = set()
    unique_jobs = []
    for job in all_jobs:
        if job['job_id'] not in seen_ids:
            seen_ids.add(job['job_id'])
            unique_jobs.append(job)
    
    print(f"Total unique jobs: {len(unique_jobs)}")
    return unique_jobs

def is_legitimate_ats(apply_url):
    if not apply_url:
        return False
    
    if any(blocked in apply_url.lower() for blocked in BLOCKED_PLATFORMS):
        return False
    
    return any(ats in apply_url.lower() for ats in LEGITIMATE_ATS)

def filter_job(job_data):
    title = job_data.get('title', '').lower()
    description = job_data.get('description', '').lower()
    location = job_data.get('location', {}).get('display_name', '').lower()
    apply_url = job_data.get('redirect_url', '')
    
    if not any(kw in title or kw in description for kw in REQUIRED_KEYWORDS):
        return False, "Not cloud/devops role"
    
    for exclude in EXCLUDE_KEYWORDS:
        if exclude in title:
            return False, f"Excluded keyword: {exclude}"
    
    # Check for clearance requirements - delete this block if you deleted EXCLUDE_CLEARANCE
    combined = f"{title} {description}".lower()
    for phrase in EXCLUDE_CLEARANCE:
        if phrase and phrase in combined:
            return False, "Clearance required"
    
    if 'remote' in location or 'work from home' in description:
        return True, None
    
    if any(md in location for md in EXCLUDE_LOCATIONS):
        return False, "Excluded location"
    
    is_acceptable = any(area in location for area in ACCEPTABLE_AREAS)
    
    if not is_acceptable:
        return False, "Outside commute area"
    
    if not is_legitimate_ats(apply_url):
        return False, "Unverified platform"
    
    return True, None

def has_seen_job(job_id):
    table = dynamodb.Table(SEEN_TABLE)
    try:
        response = table.get_item(Key={'job_id': str(job_id)})
        return 'Item' in response
    except:
        return False

def mark_as_seen(job_id):
    table = dynamodb.Table(SEEN_TABLE)
    expiration = int((datetime.now() + timedelta(days=90)).timestamp())
    table.put_item(Item={
        'job_id': str(job_id),
        'seen_date': datetime.now().isoformat(),
        'expiration_time': expiration
    })

def store_job(job_data):
    table = dynamodb.Table(JOBS_TABLE)
    item = json.loads(json.dumps(job_data), parse_float=Decimal)
    item['scraped_at'] = datetime.now().isoformat()
    table.put_item(Item=item)

def send_email(filtered_jobs, stats):
    if not filtered_jobs:
        return
    
    email_body = f"{len(filtered_jobs)} New Jobs - {datetime.now().strftime('%B %d, %Y')}\n\n"
    
    for job in filtered_jobs:
        title = job.get('title', 'Unknown')
        company = job.get('company', {}).get('display_name', 'Unknown')
        location = job.get('location', {}).get('display_name', 'Unknown')
        apply_url = job.get('redirect_url', '#')
        
        email_body += f"""
{title}
{company}
{location}
Apply: {apply_url}

"""
    
    email_body += f"Found {stats['total_found']} jobs total, sent you {len(filtered_jobs)}"
    
    sns.publish(
        TopicArn=SNS_TOPIC,
        Subject=f"{len(filtered_jobs)} New Cloud/DevOps Jobs",
        Message=email_body
    )

def lambda_handler(event, context):
    try:
        print("Starting job alerts...")
        
        all_jobs = fetch_jobs_from_indeed()
        print(f"Fetched {len(all_jobs)} total jobs")
        
        filtered_jobs = []
        rejection_reasons = {}
        
        for job in all_jobs:
            job_id = str(job.get('job_id'))
            
            if has_seen_job(job_id):
                print(f"Skipping seen job: {job.get('title')}")
                continue
            
            should_include, reason = filter_job(job)
            
            if should_include:
                filtered_jobs.append(job)
                store_job(job)
                mark_as_seen(job_id)
                print(f"Included: {job.get('title')}")
            else:
                rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
                print(f"Rejected: {job.get('title')} - {reason}")
        
        stats = {
            'total_found': len(all_jobs),
            'filtered_out': len(all_jobs) - len(filtered_jobs),
            'rejection_reasons': rejection_reasons
        }
        
        print(f"Stats: {stats}")
        
        if filtered_jobs:
            send_email(filtered_jobs, stats)
        
        return {
            'statusCode': 200,
            'body': json.dumps(f'Sent {len(filtered_jobs)} jobs')
        }
        
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
