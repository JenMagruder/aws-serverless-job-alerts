# AWS Serverless Job Alert System

Automated job search system that finds jobs, filters by your criteria, and emails you daily.

## What It Does

Searches job boards daily, filters results by location and keywords, blocks duplicates, and emails you only relevant positions.

## Architecture

Lambda for job scraping and filtering. DynamoDB for job tracking. SNS for email notifications. EventBridge for daily schedule. SerpAPI for Google Jobs search. CloudFormation for infrastructure deployment.

## Requirements

AWS account with CLI configured. SerpAPI account. Python 3.11. PowerShell or Bash.

## Setup

Sign up at serpapi.com and get your free API key.

Edit lambda_function.py and update REQUIRED_KEYWORDS, EXCLUDE_KEYWORDS, EXCLUDE_LOCATIONS, ACCEPTABLE_AREAS, FAR_COMMUTE, and the searches list. Update location in params to your state.

**Important: Do not hardcode your SerpAPI key in the code. It will be set as an environment variable in the deployment step below.**

Deploy stacks in order:
```powershell
# DynamoDB tables
aws cloudformation create-stack --stack-name job-alerts-dynamodb --template-body file://infrastructure/01-dynamodb.yaml --region us-east-1

# SNS topic
aws cloudformation create-stack --stack-name job-alerts-sns --template-body file://infrastructure/02-sns.yaml --parameters ParameterKey=EmailAddress,ParameterValue=your-email@example.com --region us-east-1

# Confirm SNS subscription in your email

# Package Lambda
cd lambda/job_alerts
pip install -r requirements.txt -t .
Compress-Archive -Path * -DestinationPath ../job_alerts.zip -Force
cd ../..

# Deploy Lambda
aws cloudformation create-stack --stack-name job-alerts-lambda --template-body file://infrastructure/03-lambda.yaml --capabilities CAPABILITY_IAM --region us-east-1

# Set environment variables (replace YOUR-ACCOUNT-ID and your-serpapi-key)
aws lambda update-function-configuration --function-name job-alerts-fetch --environment "Variables={JOBS_TABLE_NAME=job-alerts-jobs,SEEN_TABLE_NAME=job-alerts-seen,SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR-ACCOUNT-ID:job-alerts-topic,MIN_SALARY=85000,SERPAPI_KEY=your-serpapi-key}" --region us-east-1

# Deploy scheduler
aws cloudformation create-stack --stack-name job-alerts-scheduler --template-body file://infrastructure/04-scheduler.yaml --region us-east-1
```

Test it:
```powershell
aws lambda invoke --function-name job-alerts-fetch --region us-east-1 output.json
aws logs tail /aws/lambda/job-alerts-fetch --since 2m --format short
```

## Cost

AWS services used stay within free tier limits. SerpAPI offers 100 free searches per month. Current configuration stays free.

## How It Works

EventBridge triggers Lambda daily. Lambda searches SerpAPI for configured job titles. Filters results by location, seniority, clearance requirements. Checks DynamoDB to skip already seen jobs. Stores new jobs in DynamoDB. Sends email via SNS with filtered results.

## Troubleshooting

No email received: Check SNS subscription is confirmed, check CloudWatch logs for errors, verify Lambda has correct environment variables.

Too many jobs: Add more exclusions to EXCLUDE_KEYWORDS, tighten ACCEPTABLE_AREAS, add more items to BLOCKED_PLATFORMS.

Too few jobs: Remove some exclusions, add more search terms, expand ACCEPTABLE_AREAS.

## License

MIT