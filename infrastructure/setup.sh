#!/bin/bash
# filepath: infrastructure/setup.sh
# =============================================================================
# AWS CLI Setup Script for CENACE PML Data Ingestion
# =============================================================================
# This script creates the AWS infrastructure for the CENACE data lake:
# - S3 bucket with lifecycle rules
# - IAM role for Lambda
# - Lambda function
# - EventBridge rule for daily trigger
# =============================================================================

set -e  # Exit on error

# Configuration
BUCKET_NAME="mexican-energy-pml-raw"
LAMBDA_FUNCTION_NAME="cenace-pml-ingestion"
LAMBDA_ROLE_NAME="cenace-lambda-role"
EVENTBRIDGE_RULE_NAME="cenace-daily-ingestion"
AWS_REGION="us-east-2"

echo "=== CENACE PML Data Ingestion - AWS Setup ==="
echo "Region: $AWS_REGION"
echo "Bucket: $BUCKET_NAME"
echo ""

# =============================================================================
# 1. Create S3 Bucket
# =============================================================================
echo "Step 1: Creating S3 bucket..."
aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$AWS_REGION" \
    --output table

echo ""

# =============================================================================
# 2. Configure Lifecycle Rules (90-day raw retention)
# =============================================================================
echo "Step 2: Configuring S3 lifecycle rules..."
aws s3api put-bucket-lifecycle-configuration \
    --bucket "$BUCKET_NAME" \
    --lifecycle-configuration file://infrastructure/lifecycle-rules.json

echo "Lifecycle rules applied."
echo ""

# =============================================================================
# 3. Create Lambda Execution Role
# =============================================================================
echo "Step 3: Creating IAM role for Lambda..."

# Check if role already exists
if aws iam get-role --role-name "$LAMBDA_ROLE_NAME" &>/dev/null; then
    echo "Role $LAMBDA_ROLE_NAME already exists."
else
    aws iam create-role \
        --role-name "$LAMBDA_ROLE_NAME" \
        --assume-role-policy-document file://infrastructure/lambda-role-policy.json \
        --output table
    echo "Role created."
fi

# Attach S3 permissions
echo "Attaching S3 permissions to role..."
aws iam attach-role-policy \
    --role-name "$LAMBDA_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

# Attach Lambda basic execution permissions
aws iam attach-role-policy \
    --role-name "$LAMBDA_ROLE_NAME" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

echo ""

# Get role ARN
LAMBDA_ROLE_ARN=$(aws iam get-role \
    --role-name "$LAMBDA_ROLE_NAME" \
    --query 'Role.Arn' \
    --output text)

echo "Lambda Role ARN: $LAMBDA_ROLE_ARN"
echo ""

# =============================================================================
# 4. Deploy Lambda Function
# =============================================================================
echo "Step 4: Deploying Lambda function..."

# Package the code first (requires zip utility)
echo "Packaging Lambda code..."
cd src
zip -r ../dist.zip ingestion utils *.py 2>/dev/null || python -m zipfile -c ../dist.zip ingestion utils *.py
cd ..

# Create Lambda function
echo "Creating Lambda function..."
aws lambda create-function \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --runtime python3.9 \
    --handler ingestion.main.lambda_handler \
    --role "$LAMBDA_ROLE_ARN" \
    --zip-file fileb://dist.zip \
    --timeout 900 \
    --memory-size 512 \
    --environment Variables="{S3_BUCKET=$BUCKET_NAME,LOOKBACK_DAYS=7}" \
    --region "$AWS_REGION" \
    --output table

echo ""

# =============================================================================
# 5. Create EventBridge Rule (Daily 06:00 UTC)
# =============================================================================
echo "Step 5: Creating EventBridge rule..."

# Create rule
aws events put-rule \
    --name "$EVENTBRIDGE_RULE_NAME" \
    --schedule-expression "cron(0 6 * * ? *)" \
    --state ENABLED \
    --description "Daily trigger for CENACE PML ingestion at 06:00 UTC"

# Get rule ARN
EVENT_RULE_ARN=$(aws events describe-rule \
    --name "$EVENTBRIDGE_RULE_NAME" \
    --query 'Arn' \
    --output text)

# Add permission for EventBridge to invoke Lambda
aws lambda add-permission \
    --function-name "$LAMBDA_FUNCTION_NAME" \
    --statement-id EventBridgeInvoke \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "$EVENT_RULE_ARN"

# Add target to rule
aws events put-targets \
    --rule "$EVENTBRIDGE_RULE_NAME" \
    --targets "Id"="1","Arn"="$(aws lambda get-function --function-name $LAMBDA_FUNCTION_NAME --query 'Configuration.FunctionArn' --output text)"

echo ""

# =============================================================================
# Summary
# =============================================================================
echo "=== Setup Complete ==="
echo ""
echo "Resources created:"
echo "  - S3 Bucket: s3://$BUCKET_NAME"
echo "  - Lambda Function: $LAMBDA_FUNCTION_NAME"
echo "  - IAM Role: $LAMBDA_ROLE_NAME"
echo "  - EventBridge Rule: $EVENTBRIDGE_RULE_NAME (daily at 06:00 UTC)"
echo ""
echo "To test the Lambda manually:"
echo "  aws lambda invoke --function-name $LAMBDA_FUNCTION_NAME --payload '{}' response.json"
echo ""
echo "To check Lambda logs:"
echo "  aws logs tail /aws/lambda/$LAMBDA_FUNCTION_NAME --follow"
echo ""
