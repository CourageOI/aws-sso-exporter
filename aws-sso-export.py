import boto3
import json
import argparse
from typing import Dict, List, Tuple, Optional
from botocore.exceptions import ClientError

class IAMIdentityCenterMigration:
    def __init__(self, source_profile: str, destination_profile: Optional[str] = None):
        """
        Initialize with source profile and optional destination profile.
        
        Args:
            source_profile (str): AWS profile name for source management account
            destination_profile (str, optional): AWS profile name for destination management account
        """
        self.source_session = boto3.Session(profile_name=source_profile)
        self.source_account_id = self._get_account_id(self.source_session)
        
        # Initialize destination session if profile provided
        self.dest_session = None
        self.dest_account_id = None
        if destination_profile:
            self.dest_session = boto3.Session(profile_name=destination_profile)
            self.dest_account_id = self._get_account_id(self.dest_session)
        
        self._validate_and_init_clients()

    def _validate_and_init_clients(self):
        """Validate accounts and initialize AWS clients."""
        # Validate source account
        source_valid, source_error = self._validate_management_account(self.source_session)
        if not source_valid:
            raise ValueError(f"Source account {self.source_account_id} validation failed: {source_error}")

        # Initialize source clients
        self.source_sso = self.source_session.client('sso-admin')
        self.source_identity = self.source_session.client('identitystore')

        # Initialize destination clients if provided
        self.dest_sso = None
        self.dest_identity = None
        if self.dest_session:
            dest_valid, dest_error = self._validate_management_account(self.dest_session)
            if not dest_valid:
                raise ValueError(f"Destination account {self.dest_account_id} validation failed: {dest_error}")
            
            self.dest_sso = self.dest_session.client('sso-admin')
            self.dest_identity = self.dest_session.client('identitystore')

    def _validate_management_account(self, session) -> Tuple[bool, str]:
        """Validate that the account is a management account with IAM Identity Center access."""
        try:
            organizations = session.client('organizations')
            
            # Check if this is the management account
            org_info = organizations.describe_organization()
            account_id = self._get_account_id(session)
            
            if org_info['Organization']['MasterAccountId'] != account_id:
                return False, "Not a management account"
            
            # Check if IAM Identity Center is enabled
            sso_admin = session.client('sso-admin')
            try:
                sso_admin.list_instances()
                return True, ""
            except ClientError as e:
                if e.response['Error']['Code'] == 'AccessDeniedException':
                    return False, "IAM Identity Center is not enabled or insufficient permissions"
                raise e
                
        except ClientError as e:
            return False, f"Error validating account: {str(e)}"

    @staticmethod
    def _get_account_id(session) -> str:
        """Get AWS account ID from session."""
        return session.client('sts').get_caller_identity()['Account']

    def get_permission_sets(self) -> List[Dict]:
        """Extract all permission sets with their policies."""
        instance_arn = self._get_instance_arn(self.source_sso)
        permission_sets = []
        
        paginator = self.source_sso.get_paginator('list_permission_sets')
        for page in paginator.paginate(InstanceArn=instance_arn):
            for ps_arn in page['PermissionSets']:
                ps_details = self.source_sso.describe_permission_set(
                    InstanceArn=instance_arn,
                    PermissionSetArn=ps_arn
                )['PermissionSet']
                
                # Get inline policy
                try:
                    inline_policy = self.source_sso.get_inline_policy_for_permission_set(
                        InstanceArn=instance_arn,
                        PermissionSetArn=ps_arn
                    ).get('InlinePolicy', '')
                    ps_details['InlinePolicy'] = inline_policy
                except ClientError as e:
                    print(f"Warning: Could not get inline policy for {ps_details['Name']}: {str(e)}")
                
                # Get managed policies
                try:
                    managed_policies = self.source_sso.list_managed_policies_in_permission_set(
                        InstanceArn=instance_arn,
                        PermissionSetArn=ps_arn
                    ).get('AttachedManagedPolicies', [])
                    ps_details['ManagedPolicies'] = managed_policies
                except ClientError as e:
                    print(f"Warning: Could not get managed policies for {ps_details['Name']}: {str(e)}")
                
                permission_sets.append(ps_details)
        
        return permission_sets

    def migrate_permission_sets(self, permission_sets: List[Dict]):
        """Migrate permission sets to destination account if destination is configured."""
        if not self.dest_sso:
            raise ValueError("Destination account not configured")
            
        print(f"Migrating permission sets from account {self.source_account_id} to {self.dest_account_id}")
        
        for ps in permission_sets:
            print(f"Migrating permission set: {ps['Name']}")
            response = self.dest_sso.create_permission_set(
                Name=ps['Name'],
                Description=ps.get('Description', ''),
                InstanceArn=self._get_instance_arn(self.dest_sso),
                SessionDuration=ps.get('SessionDuration', 'PT1H')
            )
            
            # Migrate policies
            dest_ps_arn = response['PermissionSet']['PermissionSetArn']
            if ps.get('InlinePolicy'):
                self.dest_sso.put_inline_policy_to_permission_set(
                    InstanceArn=self._get_instance_arn(self.dest_sso),
                    PermissionSetArn=dest_ps_arn,
                    InlinePolicy=ps['InlinePolicy']
                )
            
            for policy in ps.get('ManagedPolicies', []):
                self.dest_sso.attach_managed_policy_to_permission_set(
                    InstanceArn=self._get_instance_arn(self.dest_sso),
                    PermissionSetArn=dest_ps_arn,
                    ManagedPolicyArn=policy['Arn']
                )

    def get_account_assignments(self) -> List[Dict]:
        """Get all account assignments."""
        instance_arn = self._get_instance_arn(self.source_sso)
        assignments = []
        
        paginator = self.source_sso.get_paginator('list_account_assignments')
        for page in paginator.paginate(InstanceArn=instance_arn):
            assignments.extend(page['AccountAssignments'])
        
        return assignments

    def migrate_assignments(self, assignments: List[Dict]):
        """Migrate assignments if destination is configured."""
        if not self.dest_sso:
            raise ValueError("Destination account not configured")
            
        print(f"Migrating assignments...")
        
        for assignment in assignments:
            print(f"Migrating assignment for account: {assignment['AccountId']}")
            self.dest_sso.create_account_assignment(
                InstanceArn=self._get_instance_arn(self.dest_sso),
                TargetId=assignment['AccountId'],
                TargetType='AWS_ACCOUNT',
                PermissionSetArn=assignment['PermissionSetArn'],
                PrincipalType=assignment['PrincipalType'],
                PrincipalId=assignment['PrincipalId']
            )

    @staticmethod
    def _get_instance_arn(client) -> str:
        """Get IAM Identity Center instance ARN."""
        instances = client.list_instances()
        if not instances['Instances']:
            raise Exception("No IAM Identity Center instance found")
        return instances['Instances'][0]['InstanceArn']

    def export_configuration(self, filename: str) -> Dict:
        """Export IAM Identity Center configuration to JSON file."""
        config = {
            'SourceAccountId': self.source_account_id,
            'PermissionSets': self.get_permission_sets(),
            'AccountAssignments': self.get_account_assignments()
        }
        
        with open(filename, 'w') as f:
            json.dump(config, f, indent=2)
            
        return config

def main():
    parser = argparse.ArgumentParser(description='IAM Identity Center Configuration Tool')
    parser.add_argument('--source-profile', required=True, 
                      help='Source AWS profile (must be management account)')
    parser.add_argument('--dest-profile', 
                      help='Optional destination AWS profile for migration')
    parser.add_argument('--output', default='identity_center_config.json',
                      help='Output file for configuration')
    parser.add_argument('--print', action='store_true',
                      help='Print configuration to console')
    
    args = parser.parse_args()
    
    try:
        # Initialize with or without destination
        migration = IAMIdentityCenterMigration(
            source_profile=args.source_profile,
            destination_profile=args.dest_profile
        )
        
        print(f"Source Account: {migration.source_account_id}")
        if args.dest_profile:
            print(f"Destination Account: {migration.dest_account_id}")
        
        # Always export configuration
        config = migration.export_configuration(args.output)
        print(f"Configuration exported to: {args.output}")
        
        if args.print:
            print("\nConfiguration:")
            print(json.dumps(config, indent=2))
        
        # Perform migration if destination profile provided
        if args.dest_profile:
            print("\nStarting migration...")
            migration.migrate_permission_sets(config['PermissionSets'])
            migration.migrate_assignments(config['AccountAssignments'])
            print("Migration completed successfully!")
            
    except Exception as e:
        print(f"Error: {str(e)}")
        raise

if __name__ == "__main__":
    main()