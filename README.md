# IAM Identity Center Migration Tool

## Overview
This Python script facilitates the migration of AWS IAM Identity Center (successor to AWS SSO) configurations between AWS accounts. It supports exporting and migrating permission sets, their associated policies, and account assignments from a source management account to a destination management account.

## Prerequisites
- Python 3.x
- boto3 library
- AWS CLI configured with profiles for source and (optionally) destination accounts
- Source and destination accounts must be management accounts with IAM Identity Center enabled
- Appropriate AWS permissions in both accounts

## Features
- Export IAM Identity Center configuration to JSON
- Migrate permission sets with their policies:
  - Inline policies
  - Managed policies
  - Session duration settings
- Migrate account assignments
- Validation of source and destination accounts
- Support for paginated results when fetching configurations

## Installation

1. Install required Python packages:
```bash
pip install boto3
```

2. Ensure your AWS credentials are configured with appropriate profiles:
```bash
aws configure --profile source-profile
aws configure --profile destination-profile  # if migrating
```

## Usage

### Basic Configuration Export
To export the IAM Identity Center configuration from a source account:

```bash
python migrate_iam.py --source-profile SOURCE_PROFILE --output config.json
```

### Migration Between Accounts
To migrate the configuration to a destination account:

```bash
python migrate_iam.py --source-profile SOURCE_PROFILE --dest-profile DEST_PROFILE --output config.json
```

### Print Configuration
To view the configuration in the console:

```bash
python migrate_iam.py --source-profile SOURCE_PROFILE --print
```

## Command Line Arguments
- `--source-profile`: (Required) AWS profile for source management account
- `--dest-profile`: (Optional) AWS profile for destination management account
- `--output`: (Optional) Output file name for configuration (default: identity_center_config.json)
- `--print`: (Optional) Print configuration to console

## Output Format
The script exports the configuration in JSON format with the following structure:

```json
{
  "SourceAccountId": "123456789012",
  "PermissionSets": [
    {
      "Name": "ExamplePermissionSet",
      "Description": "Example description",
      "SessionDuration": "PT1H",
      "InlinePolicy": "{}",
      "ManagedPolicies": []
    }
  ],
  "AccountAssignments": [
    {
      "AccountId": "123456789012",
      "PermissionSetArn": "arn:aws:...",
      "PrincipalType": "USER",
      "PrincipalId": "example-user"
    }
  ]
}
```

## Error Handling
The script includes comprehensive error handling for:
- Account validation
- IAM Identity Center access verification
- Permission set and policy operations
- Account assignment operations

## Limitations
- Both source and destination accounts must be management accounts
- IAM Identity Center must be enabled in both accounts
- Requires appropriate permissions in both accounts
- Does not migrate users and groups (only permission sets and assignments)

## Security Considerations
- Ensure proper access controls for AWS profiles
- Review migrated permission sets and assignments before applying them
- Consider the impact of permission set migrations on existing access patterns

## Troubleshooting

### Common Issues
1. "Not a management account" error:
   - Verify that the provided profile corresponds to an AWS Organizations management account

2. "IAM Identity Center is not enabled" error:
   - Ensure IAM Identity Center is enabled in the account
   - Verify appropriate permissions are granted

3. "Access Denied" errors:
   - Check AWS credentials and permissions
   - Ensure profiles have necessary IAM permissions