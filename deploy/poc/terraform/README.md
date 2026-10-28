# Terraform for the pilot

The imperative path is `../deploy.sh`. This directory is the same stack as code:
one container, one load balancer, one ECS service, two IAM roles, two security
groups, one log group, one image repository. Nothing else. No NAT gateway, no
database, no bucket, no domain, because the pilot does not need them.

Validated with Terraform 1.17.0 and AWS provider 6.70.0 against the account's
default VPC. It has **not been applied**: no credentials were used to build it,
so the first `terraform plan` you run is the first real check of the account
assumptions (default VPC present, Fargate quota, IAM permissions).

## What it creates

| Resource | Name | Why it exists |
| --- | --- | --- |
| `aws_ecr_repository` | `<name>-api` | Holds the image, scan on push, expiry for untagged layers |
| `aws_cloudwatch_log_group` | `/ecs/<name>-api` | API logs and ECS Exec session logs, 7 day retention |
| `aws_iam_role` execution | `<name>-exec` | ECR pull and CloudWatch Logs |
| `aws_iam_role` task | `<name>-task` | The four `ssmmessages` actions ECS Exec needs, nothing else |
| `aws_security_group` x2 | `<name>-alb-sg`, `<name>-task-sg` | Port 80 from your address, port 8000 from the ALB only |
| `aws_lb` + target group + listener | `<name>-alb`, `<name>-tg` | Public HTTP entry point, health check on `/health` |
| `aws_ecs_cluster` + service + task definition | `<name>`, `<name>-api` | One Fargate task, circuit breaker on, ECS Exec on |
| `terraform_data.exec_session_logging` | n/a | One `aws ecs update-service` call that turns on session logging |

Names match `deploy.sh` exactly, so `../demo.sh` and `../teardown.sh` work
unchanged against a Terraform-created stack.

## Prerequisites

- Terraform 1.6 or newer.
- AWS CLI v2 with credentials for a sandbox account. The stack needs ECR, ECS,
  ELBv2, EC2 (security groups), IAM and CloudWatch Logs permissions, and one
  provisioning step shells out to the CLI.
- Docker with a running daemon.
- On Windows, if provider downloads fail with "Access is denied" in
  `%LOCALAPPDATA%\Temp`, point Terraform's temp directory at the workspace:
  `export TMPDIR='D:\path\to\workspace\.local\tmp'`.

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
2. **ECS Exec session logging is a `terraform_data` call.** AWS provider 6.70
   does not expose `execute_command_configuration` on `aws_ecs_service`. The
   service attribute `enable_execute_command` is still Terraform-managed; only
   the `logging = OVERRIDE` half needs the CLI. Set `exec_session_logging =
   false` if you have no CLI and do not care about session logs.
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
| Apply fails at `exec_session_logging` | aws CLI not installed | `terraform apply -var='exec_session_logging=false'` |
| `The load balancer needs at least two subnets` | no default VPC in the region | pass `vpc_id` and `subnet_ids`, or pick another region |
| `task_memory ... is not valid for task_cpu` | invalid Fargate pair | the error lists the valid sizes for that CPU |
| Tasks pending, no capacity | Fargate vCPU quota, code `L-3032A538` | `aws service-quotas get-service-quota --service-code ecs --quota-code L-3032A538` |

## What this does not build

TLS, ACM, CloudFront, WAF, RDS, S3, a CI pipeline that builds the image, and
alarms. Those are the P1 and P2 items in the executive brief, section 10. This
directory is the P0 estate: the smallest stack that makes the demo a real cloud
deployment.
