# AWS Terraform and Lambda Assessment

I built this repository for the AWS and Terraform assessment. It creates two S3 buckets and a Lambda function that removes EXIF metadata from `.jpg` files uploaded to Bucket A, then saves each file to Bucket B with the same key. It also creates the two IAM users and gives each access to the bucket described in the brief.

## How it works

1. An object creation event for a `.jpg` key in Bucket A invokes the Lambda function.
2. The function reads the object, removes EXIF APP1 segments from the JPEG stream, and writes the image to Bucket B under the same key. The JPEG image data is not decoded or recompressed.
3. User A can list, read, and write objects in Bucket A. User B can list and read objects in Bucket B. Neither user receives access to the other bucket.

The Lambda uses the Python standard library and the AWS SDK included in the Lambda Python runtime. Its deployment ZIP contains only `app.py`, so it does not depend on native packages built for a particular computer.

## Repository layout

```text
.
├── lambda/
│   ├── app.py
│   └── lambda.zip
└── terraform/
    ├── main.tf
    ├── outputs.tf
    ├── provider.tf
    ├── terraform.tfvars
    └── variables.tf
```

## Prerequisites

- Terraform 1.x
- AWS CLI configured with credentials for an infrastructure provisioning identity
- An AWS account where those credentials can create S3 buckets, IAM roles and users, Lambda functions, and related policies

The provisioning identity is separate from assessment User A and User B. Supply its credentials through the normal AWS credential chain, such as an AWS profile or environment variables. Do not put access keys in this repository or in Terraform variables.

## Deploy

The bucket names in `terraform/terraform.tfvars` must be globally unique across AWS. Change them to available names before deployment if necessary.

From the repository root:

```sh
cd terraform
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
```

Terraform prints the bucket names and IAM user ARNs after deployment. The IAM users are created without access keys. Create credentials for them only through the account's normal identity and credential management process when needed.

To remove the infrastructure:

```sh
cd terraform
terraform destroy
```

The buckets have versioning enabled and are not configured for force deletion. Remove their objects and versions through the approved account process before destroying them.

## Access policy summary

User A (`user-a`) can list Bucket A and read or write its objects. User B (`user-b`) can list Bucket B and read its objects. The Lambda role can read objects in Bucket A, write objects in Bucket B, and write CloudWatch logs.

## Design notes

- S3 public access is blocked and default server-side encryption uses S3-managed keys.
- Lambda permissions allow invocation from Bucket A only, and the notification filters for `.jpg` objects.
- The function removes EXIF data without re-encoding the image, avoiding the quality loss caused by decoding and saving JPEG pixels again.
- The users receive only the permissions needed for the assessment. The Terraform provisioning identity needs separate infrastructure provisioning permissions and is not created or given credentials by this configuration.
- For production, consider replacing long-lived IAM users with federated identities and reviewing encryption, logging, retention, and deployment controls against the organization’s requirements.
