# AWS Serverless Job Alert System

I built this to eliminate the time I was spending manually searching job boards every day. This system automates the entire process using AWS serverless services so I can focus on applying instead of searching.

## What It Does

Searches job boards daily, filters results by location and keywords, blocks duplicates, and emails you only the jobs that actually match your criteria.

## Architecture

Lambda for job scraping and filtering. DynamoDB for job tracking. SNS for email notifications. EventBridge for daily schedule. SerpAPI for Google Jobs search. CloudFormation for infrastructure deployment.

## Requirements

AWS account with CLI configured. SerpAPI account. Python 3.11. PowerShell or Bash.

## Setup

Sign up at serpapi.com and get your free API key.

Open lambda_function.py. This is where all your personal configuration lives. You will update the search terms, location filters, and keyword exclusions to match what you are actually looking for. Each section has comments explaining what it controls.

The filters that matter most are EXCLUDE_KEYWORDS for titles you want to skip like senior or director, EXCLUDE_LOCATIONS for cities or states outside your area, ACCEPTABLE_AREAS for the commute zones you will actually consider, and BLOCKED_PLATFORMS for job boards you do not want results from.

Important: do not put your SerpAPI key in the code. It gets set as a Lambda environment variable during deployment.

Deploy the stacks in order:

```bash
# DynamoDB tables
aws cloudformation create-stack --stack-name job-alerts-dynamodb --template-body file://infrastructure/01-dynamodb.yaml --region us-east-1

# SNS topic
aws cloudformation create-stack --stack-name job-alerts-sns --parameters ParameterKey=EmailAddress,ParameterValue=your-email@example.com --template-body file://infrastructure/02-sns.yaml --region us-east-1

# Confirm the SNS subscription in your email before continuing

# Package Lambda
cd lambda/job_alerts
pip install -r requirements.txt -t .
Compress-Archive -Path * -DestinationPath ../job_alerts.zip -Force
cd ../..

# Deploy Lambda
aws cloudformation create-stack --stack-name job-alerts-lambda --template-body file://infrastructure/03-lambda.yaml --capabilities CAPABILITY_IAM --region us-east-1

# Set environment variables
aws lambda update-function-configuration --function-name job-alerts-fetch --environment "Variables={JOBS_TABLE_NAME=job-alerts-jobs,SEEN_TABLE_NAME=job-alerts-seen,SNS_TOPIC_ARN=arn:aws:sns:us-east-1:YOUR-ACCOUNT-ID:job-alerts-topic,MIN_SALARY=85000,SERPAPI_KEY=your-serpapi-key}" --region us-east-1

# Deploy scheduler
aws cloudformation create-stack --stack-name job-alerts-scheduler --template-body file://infrastructure/04-scheduler.yaml --region us-east-1
```

Test it once everything is deployed:

```bash
aws lambda invoke --function-name job-alerts-fetch --region us-east-1 output.json
aws logs tail /aws/lambda/job-alerts-fetch --since 2m --format short
```

If you get an email you are good to go. If not check your spam folder first. If it is not there check that your SNS subscription is confirmed, your environment variables are set correctly, and your CloudWatch logs are not showing errors.

## Cost

AWS services used stay within free tier limits. SerpAPI offers 100 free searches per month. Current configuration stays free.

## How It Works

EventBridge triggers Lambda on your schedule. Lambda searches SerpAPI for the job titles you configured. It filters results by location, seniority level, and any keywords you want to exclude. It checks DynamoDB to skip jobs you have already seen. New matches get stored in DynamoDB and emailed to you via SNS.

## Troubleshooting

No email: check your spam folder first. If it is not there confirm your SNS subscription is active, check CloudWatch logs, and verify your environment variables are set.

Too many results: add more terms to EXCLUDE_KEYWORDS, tighten ACCEPTABLE_AREAS, or add platforms to BLOCKED_PLATFORMS.

Too few results: remove some exclusions, add more search terms, or expand your location filters.

## License

MIT
