# AWS Terraform and Lambda Project

I built this repository as an AWS and Terraform project. It creates two S3 buckets and a Lambda function that removes EXIF metadata from `.jpg` files uploaded to Bucket A, then saves each cleaned file to Bucket B under the same key. It also creates two IAM users, each with access to the bucket described in the brief.

## At a glance

| Item | Detail |
| - | - |
| Terraform resources | 18, across 12 resource types |
| Terraform code | 269 lines across 4 files |
| Lambda runtime | Python 3.12, 256 MB memory, 10 second timeout |
| Deployment package | 1.3 KB (`app.py` only) |
| Unit tests | 6 (pytest) |
| CI | GitHub Actions: tests, `terraform fmt`, `terraform validate` |

## How it works

1. An object creation event for a `.jpg` key in Bucket A invokes the Lambda function.
2. The function reads the object, removes the EXIF segments from the JPEG stream and writes the result to Bucket B. The image data is not decoded or recompressed, so quality is unchanged.
3. User A can list, read and write objects in Bucket A. User B can list and read objects in Bucket B. Neither user can reach the other bucket.

The function uses the Python standard library and the AWS SDK that the Lambda Python runtime already includes. The deployment ZIP contains only `app.py`, so it has no native packages that depend on the machine that built it.

## Resources

| Area | Resources |
| - | - |
| S3 buckets | `bucket_a`, `bucket_b` |
| Versioning | `bucket_a_versioning`, `bucket_b_versioning` |
| Public access blocks | `bucket_a_block`, `bucket_b_block` |
| Default encryption | `bucket_a_encryption`, `bucket_b_encryption` |
| IAM users and policies | `user_a`, `user_b`, `user_a_bucket_access`, `user_b_bucket_access` |
| Lambda role and permissions | `lambda_role`, `lambda_policy`, `lambda_logging`, `allow_s3` |
| Processing and notification | `image_processor`, `bucket_notification` |

## Repository layout

```text
.
├── .github/workflows/ci.yml
├── lambda/
│   ├── app.py
│   └── lambda.zip
├── tests/
│   └── test_app.py
├── requirements-dev.txt
└── terraform/
    ├── main.tf
    ├── outputs.tf
    ├── provider.tf
    ├── terraform.tfvars
    └── variables.tf
```

## Prerequisites

- Terraform 1.x
- AWS CLI configured with credentials for an identity that can provision the infrastructure
- An AWS account where that identity can create S3 buckets, IAM roles and users, Lambda functions and related policies

The provisioning identity is separate from User A and User B. Supply its credentials through the normal AWS credential chain, such as a profile or environment variables. Do not put access keys in this repository or in Terraform variables.

## Deploy

Bucket names in `terraform/terraform.tfvars` must be unique across AWS. Change them to available names if necessary.

From the repository root:

```sh
cd terraform
terraform init
terraform fmt -check
terraform validate
terraform plan
terraform apply
```

Terraform prints the bucket names and IAM user ARNs when it finishes. The IAM users are created without access keys.

To remove the infrastructure, delete every object version and delete marker from both buckets, because versioning is on and force deletion is not enabled. Then run:

```sh
terraform destroy
```

## Tests

The six unit tests cover the EXIF removal logic:

- an EXIF segment is removed
- other APP1 segments, such as XMP, are kept
- escaped bytes in image scan data are preserved
- EXIF segments between progressive scans are removed
- data that is not a JPEG is rejected
- a truncated segment is rejected

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
```

GitHub Actions runs the tests on every push and pull request, along with `terraform fmt -check`, `terraform init -backend=false` and `terraform validate` using Terraform 1.9.8.

## Verified run

I deployed the stack with Terraform, tested it with a 3 MB iPhone photograph, then destroyed it, so nothing is deployed now. The Lambda ran on Python 3.12 as specified in Terraform, and the S3 upload triggered it as expected.

| Item | Result |
| - | - |
| Resources created | 18 |
| Runtime | python3.12 |
| Memory size | 256 MB |
| Duration | About 2.5 to 2.6 seconds, down from about 3.9 seconds before optimising the scan-data loop |
| Input size | 3,011,690 bytes |
| Output size | 3,001,662 bytes |
| Camera, GPS and original date fields in output | None, checked with ExifTool |
| Teardown | All 18 resources destroyed, buckets and log group removed |

The optimisation replaced a byte-by-byte Python loop with `bytes.find` to locate the next marker in the image scan data. All six unit tests passed before and after the change.

## Access policy summary

User A (`user-a`) can list Bucket A and read or write its objects. User B (`user-b`) can list Bucket B and read its objects. The Lambda role can read objects in Bucket A, write objects in Bucket B and write CloudWatch logs.

## Known limitations

- Only EXIF segments are removed. XMP and ICC colour profile segments are kept.
- The S3 suffix filter is case sensitive, so only lowercase `.jpg` keys trigger the function. `.jpeg`, `.JPG` and HEIC files are not processed.
- The function reads each object fully into memory and has a 10 second timeout, so very large images may fail.
- Invalid JPEG input raises an error and nothing is written to Bucket B.

## Design notes

- Public access is blocked on both buckets, and default server-side encryption uses S3-managed keys.
- Lambda invocation is permitted from Bucket A only, and the notification filters for `.jpg` objects.
- Removing EXIF without re-encoding avoids the quality loss that comes from decoding and saving JPEG pixels again.
- The ZIP contains no third-party libraries. An earlier package that bundled Pillow failed on Lambda with an import error for its native module, so the function parses the JPEG segments directly.
- The users receive only the permissions the brief asks for. The provisioning identity is separate and is not created by this configuration.
- For production, I would replace long-lived IAM users with federated identities and review encryption, logging, retention and deployment controls.
