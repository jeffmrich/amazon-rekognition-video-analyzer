# Using Rekognition Custom Labels

## Prerequisites

### S3 Bucket

1. Create an S3 bucket for the customer training images.
2. Apply the following bucket policy:
>__NOTE:__ Replace `<BUCKET NAME>` with the name of your S3 Bucket.
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AWSRekognitionS3AclBucketRead20191011",
            "Effect": "Allow",
            "Principal": {
                "Service": "rekognition.amazonaws.com"
            },
            "Action": [
                "s3:GetBucketAcl",
                "s3:GetBucketLocation"
            ],
            "Resource": "arn:aws:s3:::<BUCKET NAME>"
        },
        {
            "Sid": "AWSRekognitionS3GetBucket20191011",
            "Effect": "Allow",
            "Principal": {
                "Service": "rekognition.amazonaws.com"
            },
            "Action": [
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectVersion",
                "s3:GetObjectTagging"
            ],
            "Resource": "arn:aws:s3:::<BUCKET NAME>/*"
        },
        {
            "Sid": "AWSRekognitionS3ACLBucketWrite20191011",
            "Effect": "Allow",
            "Principal": {
                "Service": "rekognition.amazonaws.com"
            },
            "Action": "s3:GetBucketAcl",
            "Resource": "arn:aws:s3:::<BUCKET NAME>"
        },
        {
            "Sid": "AWSRekognitionS3PutObject20191011",
            "Effect": "Allow",
            "Principal": {
                "Service": "rekognition.amazonaws.com"
            },
            "Action": "s3:PutObject",
            "Resource": "arn:aws:s3:::<BUCKET NAME>/*",
            "Condition": {
                "StringEquals": {
                    "s3:x-amz-acl": "bucket-owner-full-control"
                }
            }
        }
    ]
}
```

### EC2 Instance

Using the AWS Console for EC2, perform the following tasks:

1. Create an EC2 instance, recommend m5.xlarge or better, making sure to provide a minimum of *70GB* of EBS storage.
2. Connect to the EC2 instance and ensure the following are configured:
    - AWS CLI 
    - AWS CLI Credentials with S3 Read/Write policy
    - Python >= 3.7
3. Clone this GitHub repository.

### Amazon Rekognition

Using the Rekognition console, perform the following tasks:

1. Click **Use Custom Labels** on the left navigation panel.
2. Click **Get Started**.
3. In the **Create project** section, provide a**Project name**. e.g. `boats`
4. Click **Create project**.

## Configure Datasets

On the EC2 instance, execute the following to prepare the **COCO* dataset for the custom project.

1. Chnage the to cloned GitHub repository.
2. Configure Python:
```shell
python -m venv .venv && \
source .venv/bin/activate
```
3. Configure the Python Libraries:
```shell
pip install --upgrade pip &&\
pip install -r requirements.txt
```
4. Prepare the customer COCO catgory. e.g. `boat`  
__NOTE:__ Be sure to replace `<S3 BUCKET>` with the name of the bucket created in the prerequsiites section.  
```shell
cd custom &&\
python prepare_coco.py --download-dir ./coco_dataset --categories boat --bucket <S3 BUCKET>
```  
5. Executing the command will download the COCO dataset, create a custom manifest file for all images with a `boat` and upload the manifest file to the S3 Bucket. The command will also return an `s3 sync` command as well as the *S3 URL* path to the custom manifest file.  
__NOTE:__ Make sure to note these output commands as a they will be used later.  
6. Execute the `s3 sync` command from the output above to upload the COCO images to the S3 Bucket.

__NOTE:__ To create a custom dataset for another catagegory, e.g. `truck`, run the following command `python prepare_coco.py --no-download --download-dir ./coco_dataset --categories truck --bucket <S3 BUCKET>`.

## Create a Rekognition Custom Dataset and Model

### Dataset

Use the Rekognition Console to run **Steps 7 - 15** from the [Creating a Manifest File](https://docs.aws.amazon.com/rekognition/latest/customlabels-dg/cd-manifest-files.html) documentation, using the output captured from the above process. Use the following parameters and click **Submit**:

- **Dataset name:** `boats`
- **Import images labeled by Amazon SageMaker Ground Truth**
- **.manifest location:** S3 URI for the manifest file created in the previous step

### Custom Model

1. Once the Dataset has been created, click the **Train Model** button.
2. Under **Training details --> Choose training datatset**, select the `boats` dataset.
3. Under **Training details --> Create test set**, click on **Split training dataset**.
4. Click **Train**. 

__NOTE:__ Once the mode has completed training, make sure to capture the model's version ARN.

## Deploying the Solution with a Custom Model

Follow the instructions in the main `README.md` of the repository. However, before deploying the solution, make sure to add the custom model ARN to `line 96` of the `lambda/framefetcher/framefecther.py` Lambda Function.