# Deploying the Recruiter Agent to AWS Elastic Beanstalk

This guide provides instructions for setting up and deploying the Python Recruiter Agent to AWS Elastic Beanstalk with auto-scaling capabilities.

## Recommended Names
- GitHub Repository: `recruiter-agent-server`
- Elastic Beanstalk Application: `recruiter-agent-app`
- Elastic Beanstalk Environment: `recruiter-agent-prod`

## Prerequisites
- AWS Account with appropriate permissions
- AWS CLI installed and configured
- GitHub repository with the code
- GitHub Actions secrets configured

## GitHub Actions Secrets Setup
Set the following secrets in your GitHub repository:

- `AWS_ACCESS_KEY_ID` - AWS access key with appropriate permissions
- `AWS_SECRET_ACCESS_KEY` - AWS secret access key
- `AWS_REGION` - AWS region (e.g., us-west-2)
- `EB_APPLICATION_NAME` - Elastic Beanstalk application name (e.g., recruiter-agent-app)
- `EB_ENVIRONMENT_NAME` - Elastic Beanstalk environment name (e.g., recruiter-agent-prod)

## Creating the Elastic Beanstalk Environment

### 1. Create the Application
```bash
aws elasticbeanstalk create-application --application-name recruiter-agent-app --description "Recruiter Agent Python Server"
```

### 2. Create a Solution Stack
```bash
# List available Python solution stacks
aws elasticbeanstalk list-available-solution-stacks | grep Python

# Create the environment with a Python solution stack
aws elasticbeanstalk create-environment \
  --application-name recruiter-agent-app \
  --environment-name recruiter-agent-prod \
  --solution-stack-name "64bit Amazon Linux 2023 v4.0.8 running Python 3.11" \
  --option-settings file://eb-config.json
```

### 3. Create a eb-config.json file with recommended settings:
```json
[
  {
    "Namespace": "aws:elasticbeanstalk:environment",
    "OptionName": "EnvironmentType",
    "Value": "LoadBalanced"
  },
  {
    "Namespace": "aws:autoscaling:launchconfiguration",
    "OptionName": "InstanceType",
    "Value": "t3.small"
  },
  {
    "Namespace": "aws:autoscaling:asg",
    "OptionName": "MinSize",
    "Value": "1"
  },
  {
    "Namespace": "aws:autoscaling:asg",
    "OptionName": "MaxSize",
    "Value": "4"
  },
  {
    "Namespace": "aws:elasticbeanstalk:application:environment",
    "OptionName": "PYTHONPATH",
    "Value": "."
  }
]
```

## Auto-Scaling Recommendations

### Auto-Scaling Configuration
Create a `.ebextensions/autoscaling.config` file in your repository with these settings:

```yaml
Resources:
  AWSEBAutoScalingGroup:
    Type: "AWS::AutoScaling::AutoScalingGroup"
    Properties:
      HealthCheckType: ELB
      HealthCheckGracePeriod: 300
  
  WebServerScaleUpPolicy:
    Type: "AWS::AutoScaling::ScalingPolicy"
    Properties:
      AdjustmentType: ChangeInCapacity
      AutoScalingGroupName: { "Ref": "AWSEBAutoScalingGroup" }
      Cooldown: 300
      ScalingAdjustment: 1

  WebServerScaleDownPolicy:
    Type: "AWS::AutoScaling::ScalingPolicy"
    Properties:
      AdjustmentType: ChangeInCapacity
      AutoScalingGroupName: { "Ref": "AWSEBAutoScalingGroup" }
      Cooldown: 300
      ScalingAdjustment: -1

  CPUHighAlarm:
    Type: "AWS::CloudWatch::Alarm"
    Properties:
      AlarmDescription: "Scale up if CPU > 70% for 5 minutes"
      MetricName: CPUUtilization
      Namespace: AWS/EC2
      Statistic: Average
      Period: 300
      EvaluationPeriods: 2
      Threshold: 70
      AlarmActions:
        - { "Ref": "WebServerScaleUpPolicy" }
      Dimensions:
        - Name: AutoScalingGroupName
          Value: { "Ref": "AWSEBAutoScalingGroup" }
      ComparisonOperator: GreaterThanThreshold

  CPULowAlarm:
    Type: "AWS::CloudWatch::Alarm"
    Properties:
      AlarmDescription: "Scale down if CPU < 30% for 10 minutes"
      MetricName: CPUUtilization
      Namespace: AWS/EC2
      Statistic: Average
      Period: 300
      EvaluationPeriods: 2
      Threshold: 30
      AlarmActions:
        - { "Ref": "WebServerScaleDownPolicy" }
      Dimensions:
        - Name: AutoScalingGroupName
          Value: { "Ref": "AWSEBAutoScalingGroup" }
      ComparisonOperator: LessThanThreshold
```

## Testing Auto-Scaling

To test the auto-scaling capabilities, use the following approaches:

### 1. Load Testing
Use load testing tools like Locust or Apache JMeter to simulate high traffic:

```bash
# Install locust
pip install locust

# Create a locustfile.py with request patterns
# Run with:
locust -f locustfile.py --host=https://your-eb-environment-url.elasticbeanstalk.com
```

### 2. CPU Stress Test
SSH into an EC2 instance in your environment and run:

```bash
# Install stress tool
sudo amazon-linux-extras install epel -y
sudo yum install stress -y

# Run stress test (adjust parameters as needed)
stress --cpu 2 --timeout 300
```

### 3. Monitor Scaling Events
Monitor auto-scaling activities in the AWS Management Console:

1. Navigate to EC2 → Auto Scaling Groups
2. Select your environment's Auto Scaling Group
3. Check the "Activity" and "Monitoring" tabs to observe scaling activities

### 4. CloudWatch Alarms
Monitor the CloudWatch alarms created for your auto-scaling policies:

1. Navigate to CloudWatch → Alarms
2. Check the status of CPU high and low alarms
3. View the alarm history to see when thresholds were breached

## Performance Monitoring

Set up enhanced monitoring to track performance:

```bash
aws elasticbeanstalk update-environment \
  --application-name recruiter-agent-app \
  --environment-name recruiter-agent-prod \
  --option-settings "[
    {
      \"Namespace\": \"aws:elasticbeanstalk:healthreporting:system\",
      \"OptionName\": \"SystemType\",
      \"Value\": \"enhanced\"
    }
  ]"
```

## Deployment
Push your code to the master branch, and the GitHub Actions workflow will automatically deploy to Elastic Beanstalk.