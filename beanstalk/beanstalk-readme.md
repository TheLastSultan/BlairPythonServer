# AWS Elastic Beanstalk Config

To summarize, AWS Elastic Beanstalk uses the concept of "Application Versions"
to track changes. Everything inside this directory is zipped up, and 
uploaded to AWS Elastic Beanstalk to run RocketHire. 

Files in this directory:
* `.platform/.../01login.sh`: This is an AWS Platform Hook that is executed on bootup. It logs into AWS ECR.
* `docker-compose.yml`: Tells AWS where to find the RocketHire docker images.
* `beanstalk_recompose.py`: Looks at the current /docker-compose.yaml file, and generates the `/beanstalk/docker-compose.yml`.

### When do I need to create a new Application Version?
If and only if anything in this directory changes.

### How do I create a new Application Version?
1. Compress all the files in this directory. Make sure that you're not compressing the beanstalk folder itself. 
   Meaning, if you unzip the directory, you should see the files and not a folder with the files inside. 
   This is really important, and has cost me a lot of time. In MacOS, in Finder, go to this directory then press 
   cmd-a followed by right click -> compress.
2. Go to AWS Console > Elastic Beanstalk > Applications > RocketHire > Create New App Version > upload zip. Alternatively you can also upload to AWS S3 and run the command below.
4. Run `./scripts/deploy.sh` in console to redeploy with the new App Version.

### Useful AWS CLI Commands, if that's your style.
```bash
# Create App Version
aws elasticbeanstalk create-application-version --application-name $NAME --version-label $VERSION --source-bundle S3Bucket=$EB_BUCKET,S3Key=$ZIP
# Deploy to running instances.
aws elasticbeanstalk update-environment --environment-name $ENV --version-label $VERSION
```