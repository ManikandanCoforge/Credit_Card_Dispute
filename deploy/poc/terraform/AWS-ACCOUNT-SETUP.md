# AWS account setup, step by step

This is your half. Everything here is either a decision, a guardrail, or a credential. I run the
Terraform and the seven beats; you run these steps first, because each one is something only the
account owner should do.

| Step | Who | Your time | Billable? |
| --- | --- | --- | --- |
| 0. Pick the isolation route | you | 2 min | no |
| 1. Confirm account and region | you | 2 min | no |
| 2. Turn on guardrails | you | 5 min | no |
| 3. Decide how the pilot gets credentials | you | 5 min | no |
| 4. Fill in .env | you | 1 min | no |
| 5. Preflight, then stop | me | 1 min | no |
| 6. Install the Session Manager plugin | you, one UAC click | 3 min | no |
| 7. Approve the six phases | you | 25 min elapsed | yes, about $0.056/hour |
| 8. Verify and demo | both | 20 min | same |
| 9. Teardown | me, you approve | 3 min | stops billing |

Your total: about 20 minutes.

## 0. Pick the isolation route

| Route | Choose it when | What that changes |
| --- | --- | --- |
| Dedicated VPC in this account | you cannot cut a member account tonight | add `TF_VAR_create_vpc=true` to .env |
| Separate member account | you have management-account access and a spare email alias | nothing, the stack is identical |
| Shared default VPC | only if you accept the caveats I listed | nothing |

Decision rule: if this account already holds workloads you do not own, use the dedicated VPC at
minimum. It costs nothing extra and keeps the pilot's load balancer and task out of subnets that
other teams also use.

``
I am choosing: [ ] dedicated VPC in this account    [ ] new member account
``

## 1. Confirm you are in the right account and region

Open Git Bash in the repository and put the bundled AWS CLI on the path for this shell:

```bash
cd /path/to/credit-card-dispute
export PATH="$PWD/.local/tools/awscli/Amazon/AWSCLIV2:$PATH"
aws --version                 # expect aws-cli/2.39.0
aws sts get-caller-identity
```

Good looks like: `Account` is the account you intend to spend in, and `Arn` names your
user or an assumed role. Wrong account, stop here, nothing exists yet.

Region, because every resource below is regional:

```bash
aws configure get region      # expect us-east-1
aws configure set region us-east-1   # only if it is blank or wrong
```

The Terraform defaults to us-east-1. If you deploy elsewhere, also set `AWS_REGION` and
`AWS_DEFAULT_REGION` in .env, and note the prices in the brief are us-east-1.

## 2. Guardrails, before anything exists

### 2.1 A budget that emails you

Console: **Billing and Cost Management, Budgets, Create budget, Monthly cost budget**. Set
25 USD, use your work email. This is the only thing that tells you a resource was left running
next week.

A budget cannot stop ECS. It is an alarm, not a kill switch. The kill switch is
`./phases.sh destroy`.

### 2.2 Activate the cost allocation tag

Console: **Billing and Cost Management, Cost allocation tags**, activate `Project`. Everything
this stack creates already carries `Project=credit-card-dispute`, so activating the tag puts
the pilot's cents on their own line instead of blending into the account total. It can take up to
24 hours to appear in Cost Explorer. That is expected.

### 2.3 The two quotas that can fail a deploy

```bash
aws service-quotas get-service-quota --service-code fargate \
  --quota-code L-3032A538 --query 'Quota.{Name:QuotaName,Value:Value}'
```

The pilot asks for 0.5 vCPU. A value of 0 means request an increase first, otherwise this fails
15 minutes into the deploy and looks like a scheduling bug.

Application Load Balancers: **Service Quotas, Elastic Load Balancing v2, Load balancers per
region**, default 50. If the account is near the ceiling, the `edge` phase fails after the
image is already pushed. Delete something or request an increase.

### 2.4 Confirm the network starting point

```bash
aws ec2 describe-vpcs --filters Name=is-default,Values=true \
  --query 'Vpcs[].{VpcId:VpcId,Cidr:CidrBlock,State:State}'
```

Non-empty: the default-VPC route works. Empty, which happens in accounts created with a
default-VPC restriction: use `TF_VAR_create_vpc=true` in step 4 and the stack builds its own.

## 3. Decide how the pilot gets credentials

Three options, in order of hygiene. Pick the first you can finish in ten minutes.

### Option A, session credentials from an assumed role (best)

Use this if the account is federated or uses SSO. Nothing long lived touches the disk.

```bash
aws sts assume-role --role-arn arn:aws:iam::<account-id>:role/<pilot-admin-role> \
  --role-session-name ccdpoc --duration-seconds 3600
```

Copy the three values from the response into .env in step 4. They expire in an hour, and when
they do, `phases.sh` fails on an auth error instead of silently doing nothing.

### Option B, a scoped IAM user for the pilot

Console: **IAM, Users, Create user**, name `ccd-poc-deployer`, no console access. Attach these
AWS managed policies, which cover exactly the services the stack touches:

- `AmazonEC2ContainerRegistryFullAccess`
- `AmazonECS_FullAccess`
- `ElasticLoadBalancingFullAccess`
- `IAMFullAccess`, plus a pass-role boundary check by you, since the stack creates two roles
- `CloudWatchLogsFullAccess`
- `AmazonSSMFullAccess`, for the ECS Exec operator channel
- `SecretsManagerReadWrite` is not needed, do not attach it

These are broader than the pilot needs, which is the trade for not hand-maintaining a policy
document. If you want the tight inline policy instead, ask me and I will generate it from the
Terraform resource list.

Then **Security credentials, Create access key, Command Line Interface (CLI)**. That gives you the
two values for step 4. This identity can create and delete the pilot and nothing outside it, so a
leak costs a destroyed sandbox, not an account.

### Option C, your existing admin key (fastest, least tidy)

It works, because admin covers everything above. Understand the trade: the key is broader than the
pilot, it does not expire, and CloudTrail attributes every pilot action to it. Fine for a demo you
are sitting in front of, not something to leave in a file for a week.

``
Using: [ ] A assumed role   [ ] B scoped user   [ ] C existing admin key
``


### 3.1 Where the three values actually come from

Console, top right, **sign-in name, Security credentials** takes you to IAM. From there, three
different situations, pick the one that matches how you sign in today.

| How you sign in to the console | Where the key comes from | Expires |
| --- | --- | --- |
| IAM user with a password | IAM, Users, your user, Security credentials, Access keys, Create access key | never, until you deactivate it |
| SSO, federated, or a role you switch into | IAM Identity Center portal, Command line or programmatic access | 1 to 12 hours |
| Admin role you can assume from a working profile | `aws sts assume-role`, or `aws configure export-credentials` | 1 hour by default |

**IAM user access key, click by click**

1. Console, search `IAM`, then **Users**, then your user name.
2. **Security credentials** tab, scroll to **Access keys**, **Create access key**.
3. Use case: **Command Line Interface (CLI)**, tick the warning, **Next**.
4. Optional description, **Create access key**.
5. The next page shows **Access key** and **Secret access key**. This is the only time the secret is
   displayed. **Download .csv** or copy both values now. If you lose the secret, deactivate the key
   and create another, there is no way to read it again.
6. That page does not show a session token, because a user key is permanent. Leave
   `AWS_SESSION_TOKEN` empty.

**SSO or federated sign-in, no access keys exist**

1. Console, search `IAM Identity Center`, **Users**, your user, copy the **AWS access portal URL**.
2. Sign in there, pick the account and role, then **Command line or programmatic access**.
3. The dialog offers **Option 1: Set AWS environment variables**. It shows exactly three exports:
   `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`. Copy all three, session token
   included, into .env.
4. They expire in hours. When they do, `phases.sh` fails with an auth error, and you repeat this
   step. That is the correct behaviour, not a bug.

**From something that already works**

If the CLI already works on this machine under some profile:

```bash
export PATH="$PWD/.local/tools/awscli/Amazon/AWSCLIV2:$PATH"
aws configure list
aws sts get-caller-identity --profile <existing-profile>
aws configure export-credentials --profile <existing-profile> --format env
```

The last command prints the three exports to paste into .env, temporary token included when the
profile uses one. CloudShell in the console does the same thing without any local setup.

**Two blockers to expect in a corporate account**

- An SCP or permissions boundary may deny `iam:CreateAccessKey` outright. If **Create access key**
  is greyed out or fails, that is policy, not your admin rights, and the SSO route is the way in.
- A policy may require MFA for API calls, in which case a fresh access key fails with AccessDenied
  until you use a session that carries MFA. Again, SSO or `assume-role` with MFA solves it.

**Never the account root user.** Root access keys are the one mistake that turns a $0.45 demo into an
incident. If the only credentials you have are root, tell me and we create a proper identity first.

## 4. Fill in .env

```bash
cp .env.example .env
```

Edit .env and set exactly these:

```bash
AWS_ACCESS_KEY_ID=<from step 3>
AWS_SECRET_ACCESS_KEY=<from step 3>
AWS_SESSION_TOKEN=<option A only, otherwise leave empty>
AWS_REGION=us-east-1
AWS_DEFAULT_REGION=us-east-1
```

If you chose the dedicated VPC in step 0, also uncomment `TF_VAR_create_vpc=true`.

Then prove the file cannot be committed:

```bash
git check-ignore -v .env      # expect .gitignore:28:.env
```

If that prints nothing, stop and tell me. A tracked .env would fail the repo's env-files CI job
and put your key in a diff.

## 5. Preflight, then stop

Tell me the file is ready. I run `cd deploy/poc/terraform && ./phases.sh preflight`.

It creates nothing. It prints the Terraform and CLI versions, then `sts get-caller-identity`
using the key in .env: account id, ARN, and account alias if the account has one. I show you that
output and stop. You confirm it is the account you meant, and only then does anything get created.

## 6. Install the Session Manager plugin

Needed for two of seven beats: approving a review inside the running task, and reading the audit
trail from the container. The deploy works without it, beats 4 and 7 do not.

The installer is already downloaded at `.local/tools/SessionManagerPluginSetup.exe`. It needs
elevation, which is the one thing I cannot do for you. Double-click it, allow UAC, click through.

```bash
export PATH="$PWD/.local/tools/bin:$PATH"
session-manager-plugin --version
```

Not found? Tell me and I copy the binary from
`C:\Program Files\Amazon\SessionManagerPlugin\bin\` into `.local/tools/bin`.

## 7. Approve the six phases

About 25 minutes of wall clock, most of it waiting on the load balancer and the service.

| Phase | Creates | Cost exposure |
| --- | --- | --- |
| registry | ECR repository | cents of storage for a 342 MB image |
| core | log group, two IAM roles, two security groups | effectively zero |
| image | the push itself | cents |
| edge | ALB, target group, listener | $0.0225/hour, billing starts here |
| service | cluster, task definition, Fargate task | $0.0247/hour at 0.5 vCPU and 1 GB |
| verify | nothing | reads only |

From the moment `edge` finishes the meter runs at about $0.056/hour, which is $0.45 for an
8-hour demo day. `service` needs about two minutes to stabilise because of the 90-second
health check grace period. Do not judge it in the first 30 seconds.

## 8. Verify and demo

I run the five checks in the Terraform README: health over the public DNS name, target health
`healthy`, the ECS Exec managed agent `RUNNING`, the scored run inside the container, and
the audit read through Exec. Then the seven beats, then teardown. Nothing here needs you to touch
a resource by hand, and nothing survives the teardown.

## 9. Teardown

```bash
cd deploy/poc/terraform && ./phases.sh destroy
```

Order matters: service before cluster so Fargate billing stops, ALB before its security groups,
ECR repository with force delete because it holds an image.

Prove nothing billable is left, in one command:

```bash
aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=credit-card-dispute \
  --query 'ResourceTagMappingList[].ResourceARN'
```

An empty list is the claim. Anything still in the list is a resource the destroy missed, and I
want to see it.

## 10. When something fails

| Error | Meaning | Fix |
| --- | --- | --- |
| AccessDenied on iam:CreateRole | an SCP or permission boundary forbids it, admin or not | use a role granted by the boundary owner, or a member account |
| InvalidClientTokenId | wrong key, or the token does not belong to it | re-copy the whole export block, then check the lengths: key 20, secret 40 |
| ExpiredToken mid-deploy | console-exported session credentials last one hour, and a phased rollout can straddle that | refresh the block in `.env` and rerun the phase; `phases.sh` is idempotent. For a demo that must not die on the hour, use a long-lived IAM user key from step 3 instead |
| OptInRequired | the region is not enabled for the account | deploy in us-east-1, or enable the region |
| VcpuLimitExceeded | Fargate quota is 0 | request the increase from step 2.3 |
| needs at least two subnets | no default VPC | set TF_VAR_create_vpc=true (mandatory in account 104005345381, which has no default VPC) |
| CannotPullContainerError | image architecture mismatch | the scripts pick the platform, tell me |
| ALB returns 503 | task not healthy yet | wait two minutes, then check target health |

## Console paths, if you would rather click than type

| Task | Path |
| --- | --- |
| Budget | Billing and Cost Management, Budgets, Create budget |
| Cost tags | Billing and Cost Management, Cost allocation tags |
| Quotas | Service Quotas, AWS services, Fargate, or Elastic Load Balancing |
| IAM user and key | IAM, Users, ccd-poc-deployer, Security credentials |
| See the stack running | ECS, Clusters, ccd-poc, Services, ccd-poc-api |
| See the spend | Billing, Cost Explorer, group by tag Project |
| Operator sessions | CloudWatch, Log groups, /ecs/ccd-poc-api |
## Appendix, the shared default VPC route in detail

Use this only after reading the caveats. Everything below is read only until step 8.

### A.1 Check what you are inheriting

```bash
VPC=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true --query 'Vpcs[0].VpcId' --output text)
echo "default VPC: $VPC"

aws ec2 describe-subnets --filters Name=vpc-id,Values=$VPC Name=default-for-az,Values=true \
  --query 'Subnets[].{Subnet:SubnetId,AZ:AvailabilityZone,Cidr:CidrBlock,FreeIPs:AvailableIpAddressCount}' \
  --output table
```

You need at least two subnets in two different AZs. Each row also tells you how many free addresses
are left in that subnet, which matters if other teams are launching instances there.

```bash
# The main route table must have a default route to an internet gateway.
aws ec2 describe-route-tables --filters Name=vpc-id,Values=$VPC Name=association.main,Values=true \
  --query 'RouteTables[0].Routes[].{Dest:DestinationCidrBlock,Gw:GatewayId,State:State}' --output table

# Which network ACLs are attached. Default allow-all is what you want to see.
aws ec2 describe-network-acls --filters Name=vpc-id,Values=$VPC \
  --query 'NetworkAcls[].{Id:NetworkAclId,Default:IsDefault}' --output table
```

### A.2 Check for collisions with your own names

```bash
aws ec2 describe-security-groups \
  --filters Name=group-name,Values=ccd-poc-alb-sg,ccd-poc-task-sg \
  --query 'SecurityGroups[].{Name:GroupName,Id:GroupId}' --output table

aws iam get-role --role-name ccd-poc-task 2>&1 | head -2      # want NoSuchEntity
aws iam get-role --role-name ccd-poc-exec 2>&1 | head -2

aws resourcegroupstaggingapi get-resources \
  --tag-filters Key=Project,Values=credit-card-dispute \
  --query 'ResourceTagMappingList[].ResourceARN'
```

Every one of those must come back empty or NoSuchEntity. Anything else means the name is already
taken and the apply will fail partway, after the log group exists.

### A.3 Check headroom

```bash
aws service-quotas get-service-quota --service-code fargate --quota-code L-3032A538 \
  --query 'Quota.Value'

aws elbv2 describe-load-balancers --query 'length(LoadBalancers)'
```

Fargate vCPU must be above 0.5. If the load balancer count is near the account limit, the edge phase
is the one that fails, and it fails after the image has been pushed.

### A.4 Then the normal path

Steps 3 to 9 of the main guide, unchanged. No `TF_VAR_create_vpc` line in .env.

## The caveats, ranked by what actually bites

| Hazard | What happens | How you notice | Mitigation |
| --- | --- | --- | --- |
| Org guardrails, SCPs or AWS Config auto remediation | A landed zone rule deletes or flags internet facing resources, or an SCP denies the create | apply fails with AccessDenied, or a resource disappears minutes after creation | ask the platform owner before you deploy, or use a member account |
| Public IP denied by policy | Fargate task cannot reach ECR, service never stabilises | service stuck at 0 running tasks, CannotPullContainerError in logs | no pilot route works without public IPs, a NAT gateway at $32.85 a month is the only alternative |
| Shared subnet NACL or route table changed by another team | ALB unreachable, or task loses egress | target unhealthy, health check timeouts, 503 | A.1 checks before, and re-check if something unexplained fails |
| Quota shared with everyone else | deploy fails halfway through | VcpuLimitExceeded, TooManyLoadBalancers | A.3 checks, and request earlier |
| Someone deletes the default VPC with a cleanup script | your load balancer and task vanish with it | resources gone, ALB DNS stops resolving | dedicated VPC route instead |
| Security review noise | GuardDuty, Security Hub or a human notices a public ALB in a shared account | an email you did not ask for | one day lifetime, tag Project, teardown, and tell the owner first |
| Billing and chargeback | the spend appears in a shared account | FinOps question | activate the Project tag, and $0.45 is easy to explain |
| Name and IAM collisions | apply fails on an existing role or security group | AlreadyExists | A.2 checks |

The honest summary: in a corporate account the technical hazards are all manageable, and the
organisational ones are the ones that decide whether you deploy. A dedicated VPC fixes the subnet,
NACL and route table rows. It does not fix SCPs, Config rules, public IP policy or a security team
that wants to know first. Those are a conversation, not a Terraform variable.