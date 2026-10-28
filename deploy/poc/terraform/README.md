# Terraform for the pilot

The imperative path is `../deploy.sh`. This directory is the same stack as code:
one container, one load balancer, one ECS service, two IAM roles, two security
groups, one log group, one image repository. Nothing else. No NAT gateway, no
database, no bucket, no domain, because the pilot does not need them.

Validated with Terraform 1.17.0 and AWS provider 6.70.0. It was applied on
28 October 2026 in `us-east-1`: 26 resources in a dedicated VPC, with the image
built from commit `c7ea9b2`. On a fresh account, run `./phases.sh preflight` and
read the plan before applying; the plan is still the first real check of the
account's quotas and IAM permissions.

If you are the account owner and want the account-side steps, the budget, the
quota checks, the credentials and the teardown proof, follow
[AWS-ACCOUNT-SETUP.md](AWS-ACCOUNT-SETUP.md) first. It is written for you, not
for the deployer.

## What it creates

| Resource | Name | Why it exists |
| --- | --- | --- |
| `aws_ecr_repository` | `<name>-api` | Holds the image, scan on push, expiry for untagged layers |
| `aws_cloudwatch_log_group` | `/ecs/<name>-api` | API logs and ECS Exec session logs, 7 day retention |
| `aws_iam_role` execution | `<name>-exec` | ECR pull and CloudWatch Logs |
| `aws_iam_role` task | `<name>-task` | The four `ssmmessages` actions ECS Exec needs, plus writes to the Exec session log group |
| `aws_security_group` x2 | `<name>-alb-sg`, `<name>-task-sg` | Port 80 from your address, port 8000 from the ALB only |
| `aws_lb` + target group + listener | `<name>-alb`, `<name>-tg` | Public HTTP entry point, health check on `/health` |
| `aws_ecs_cluster` + service + task definition | `<name>`, `<name>-api` | One Fargate task, circuit breaker on, ECS Exec on |
| Cluster Exec logging | n/a | One `aws ecs update-cluster` call in `phases.sh` turns on session logging after the service applies. Not a Terraform resource. |
| `aws_vpc` + 2 public subnets + IGW, optional | `<name>-vpc`, `<name>-public-1`, `<name>-public-2` | Only with `create_vpc = true`. Keeps the pilot out of the account's shared default VPC |

Names match `deploy.sh` exactly, so `../demo.sh` and `../teardown.sh` work
unchanged against a Terraform-created stack.

## Prerequisites

- Terraform 1.6 or newer.
- AWS CLI v2 with credentials for a sandbox account. The stack needs ECR, ECS,
  ELBv2, EC2 (security groups), IAM and CloudWatch Logs permissions, and one
  provisioning step shells out to the CLI.
- Docker with a running daemon.
- On Windows, if provider downloads fail with "Access is denied" in
  `%LOCALAPPDATA%\Temp`, point Terraform's temp directory at the workspace. Use
  a native path with forward slashes, because an MSYS path such as `/d/...`
  makes Terraform write to `\terraform-provider...`:

  ```bash
  export TMPDIR="$(cygpath -m "$PWD/.local/tmp")"
  export TEMP="$TMPDIR" TMP="$TMPDIR"
  ```

  `phases.sh` does this for you.

## Isolating the pilot from a shared account

Nothing here creates an account or a group. By default the stack reads the
account's **default VPC** and puts its resources in those shared subnets. If the
key belongs to a work account that other people also use, that means:

- the pilot's load balancer and task sit in subnets someone else may also use,
- a new IAM role appears in an account-wide namespace,
- the bill shows in that account, separated only by tags,
- and if someone deletes the default VPC, the demo goes with it.

Three ways to make that cleaner, in increasing order of isolation:

| Route | What to do | Isolation | Effort |
| --- | --- | --- | --- |
| Dedicated VPC in the same account | `./phases.sh all` with `TF_VAR_create_vpc=true` | Own network, own CIDR (`10.42.0.0/16`), own route table | One variable |
| Dedicated account | Create a member account in Organizations, then use its credentials | Own bill, own quotas, own IAM | Needs org permission and a fresh email |
| Shared account as built | nothing | Names and tags only | zero |

A dedicated VPC adds no billable resource. It does not isolate IAM, quotas or
billing, only networking.

## Quick start

```bash
cd deploy/poc/terraform
cp terraform.tfvars.example terraform.tfvars   # optional, every value has a default
./up.sh
```

`up.sh` runs three phases and stops at the first failure:

1. `terraform init` and `apply -target=aws_ecr_repository.api`. The repository
   must exist before an image can be pushed to it.
2. `./push-image.sh`: ECR login, `docker build --platform linux/amd64`, push.
3. `terraform apply` for the rest, then it polls `/health` for up to 10 minutes.

Why the phases: an ECS service that starts before the image exists fails with
`CannotPullContainerError` and the circuit breaker rolls the deployment back.
That is a 15 minute detour for an ordering problem.

Manual equivalent:

```bash
terraform init
terraform apply -target=aws_ecr_repository.api
./push-image.sh
terraform apply
terraform output -raw api_base_url
```

## Phased rollout

`phases.sh` is the same stack split into steps you can check one at a time.
Every subcommand is idempotent, every one reads credentials from `.env` at the
repository root, and none of them echo a key.

```bash
./phases.sh preflight   # tools, identity, account alias. Creates nothing.
./phases.sh registry    # ECR repository
./phases.sh core        # log group, IAM roles, security groups
./phases.sh image       # docker build and push, 342 MB
./phases.sh edge        # load balancer, target group, listener
./phases.sh service     # cluster, task definition, service, exec logging
./phases.sh verify      # /health, target health, exec agent status
./phases.sh status      # plan only, reports pending changes
./phases.sh destroy     # stops billing
./phases.sh all         # all of the above, in order
```

Why the order: the repository must exist before the image, and the image must
exist before the service starts, otherwise the task fails with
`CannotPullContainerError` and the circuit breaker rolls the deployment back.
`edge` comes before `service` because the service registers itself into a target
group that has to exist first.

`preflight` prints the account id and alias from `aws sts get-caller-identity`.
Read them before `registry` and stop if that is not the sandbox account.

### Credentials, and where they come from

`.env` at the repository root, copied from `.env.example` and filled in. It is
git-ignored; the env-files CI job fails the build if a `.env` is ever tracked.
Terraform and the AWS CLI read `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_SESSION_TOKEN` (optional) and `AWS_REGION` from the environment; `phases.sh`
exports them for the duration of one command.

Either fill those lines in, or leave them blank and run `aws configure` once so
the keys live in `%USERPROFILE%\.aws\credentials`. `phases.sh` checks for
credentials in that order: `.env` first, then whatever profile the CLI already
has, and only fails when both are missing. One caveat for blank `.env` keys:
the shell that runs `phases.sh` must be able to see the profile, which is true
for your own Git Bash but not for a process started with a different
`HOME`/`USERPROFILE`.

### Toolchain without admin rights

This checkout keeps its tools under `.local/tools`, so nothing has to be
installed system-wide:

| Tool | Path | Notes |
| --- | --- | --- |
| Terraform | `.local/tools/terraform.exe` | 1.17.0, unzipped |
| AWS CLI v2 | `.local/tools/awscli/Amazon/AWSCLIV2/aws.exe` | administrative MSI extract, no admin needed |
| Session Manager plugin | `.local/tools/bin/session-manager-plugin.exe` | needed for ECS Exec, which the approval beat uses |

`phases.sh` puts all three on `PATH` for its own commands. Outside it, prefix
commands with `export PATH="$PWD/../../../.local/tools/awscli/Amazon/AWSCLIV2:$PATH"`.

First apply takes about 10 minutes including the provider download, the image
build and the service stabilising. The second apply after a reboot is faster.

## Verify, in this order

```bash
# 1. the service answers at all
curl -fsS "$(terraform output -raw health_url)"

# 2. the load balancer can reach the task
aws elbv2 describe-target-health \
  --target-group-arn "$(terraform output -raw target_group_arn)" \
  --query 'TargetHealthDescriptions[0].TargetHealth.State' --output text

# 3. the managed agent is RUNNING, which is what makes the approval beat work
TASK="$(aws ecs list-tasks --cluster "$(terraform output -raw cluster_name)" \
  --service-name "$(terraform output -raw service_name)" --query 'taskArns[0]' --output text)"
aws ecs describe-tasks --cluster "$(terraform output -raw cluster_name)" --tasks "$TASK" \
  --query 'tasks[0].containers[0].managedAgents[0].lastStatus' --output text

# 4. the scored run, from inside the container
../../demo.sh score

# 5. the audit trail
../../demo.sh audit
```

Check 3 is the one that predicts whether the human approval beat works. If the
managed agent is not `RUNNING`, `demo.sh exec` will fail and the approval has to
fall back to the container.

Then the seven beats:

```bash
../../demo.sh url
../../demo.sh request CARD-D01
../../demo.sh pending
../../demo.sh approve rev_xxxxxxxx --reviewer ken
../../demo.sh record rev_xxxxxxxx
../../demo.sh audit
```

## Change the code, redeploy

The tag stays `poc`, so Terraform sees no new image. Push the image, then
replace the task definition revision:

```bash
./push-image.sh
terraform apply -replace="aws_ecs_task_definition.api"
```

Or bump `image_tag` in `terraform.tfvars` and apply normally. The service rolls
one task and the circuit breaker rolls back if the new task never goes healthy.

## Teardown

```bash
./down.sh          # terraform destroy -auto-approve, about 3 minutes
```

Do not run `../teardown.sh` against a Terraform-created stack. It deletes by
name outside of state, which leaves a stale state file and orphaned resources.
Use one tool per stack.

## Cost

0.5 vCPU and 1 GB Fargate, one ALB, one public IPv4: about `$0.056` per hour,
`$0.45` for an eight hour day, `$1.35` a day if forgotten. The `Lifetime =
ephemeral` tag is there for the sweep. Figures come from the us-east-1 price
list in the executive brief, section 6.

## State

Local `terraform.tfstate`, ignored by git. It holds resource IDs, not secrets.
For a shared environment, move it to S3 with a DynamoDB lock table:

```hcl
terraform {
  backend "s3" {
    bucket         = "your-tf-state-bucket"
    key            = "ccd-poc/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}
```

## Differences from deploy.sh, and why

1. **Phased apply.** Terraform cannot build an image, so the repository is
   created first and the service after the push.
2. **ECS Exec session logging is a cluster-level CLI call in `phases.sh`.**
   AWS provider 6.70 does not expose `execute_command_configuration` on
   `aws_ecs_cluster` or `aws_ecs_service`. The service attribute
   `enable_execute_command` is Terraform-managed; the `logging = OVERRIDE`
   half is one `aws ecs update-cluster` call after the service applies. Set
   `TF_VAR_exec_session_logging=false` if you have no CLI and do not care about
   session logs.
3. **The allowlist defaults to your own address.** When `allowed_cidrs` is null,
   `checkip.amazonaws.com` is called once at plan time and the /32 is allowed.
   `deploy.sh` defaults to `0.0.0.0/0`. Pass `allowed_cidrs = ["0.0.0.0/0"]` to
   match the old behaviour for a demo where you do not know the room's IP.
4. **Tags.** `default_tags` stamps every resource with project, owner, component
   and lifetime.

## Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `CannotPullContainerError` | image not pushed, wrong tag, or wrong architecture | `./push-image.sh`, check `image_tag` and `cpu_architecture` against the build platform |
| Target stays unhealthy | container listening on loopback, or wrong port | the image runs `deploy/poc/serve.py`, which binds 0.0.0.0; check `container_port` |
| `ExecuteCommandAgent` not RUNNING | task role missing `ssmmessages`, or no init process | the stack sets both; check you did not attach a different role |
| `phase 5b` warns about Exec session logging | aws CLI missing, or `ecs:UpdateCluster` denied | install the CLI, or set `TF_VAR_exec_session_logging=false`; Exec still works without session logs |
| `The load balancer needs at least two subnets` | no default VPC in the region | set `create_vpc = true`, or pass `vpc_id` and `subnet_ids` |
| `ExpiredToken` or `RequestExpired` halfway through | temporary credentials from the console last one hour | refresh `.env`, re-run the same phase; every phase is idempotent. Use a long-lived IAM user key if the demo must outlive the hour |
| `task_memory ... is not valid for task_cpu` | invalid Fargate pair | the error lists the valid sizes for that CPU |
| Tasks pending, no capacity | Fargate vCPU quota, code `L-3032A538` | `aws service-quotas get-service-quota --service-code ecs --quota-code L-3032A538` |

## What this does not build

TLS, ACM, CloudFront, WAF, RDS, S3, a CI pipeline that builds the image, and
alarms. Those are the P1 and P2 items in the executive brief, section 10. This
directory is the P0 estate: the smallest stack that makes the demo a real cloud
deployment.
