# Terraform provisioning

Creates **`show-twilio-inner-circle-badge`** targeted at an **existing**
Twilio-synced segment key. It does not create the segment.

```bash
terraform init
terraform apply \
  -var="access_token=${LD_ACCESS_TOKEN}" \
  -var="project_key=${LD_PROJECT_KEY}" \
  -var="environment_key=${LD_ENVIRONMENT_KEY}" \
  -var="synced_segment_key=${LD_TWILIO_SEGMENT_KEY:-marcoly-twilio-inner-circle}"
```

The segment must already exist (Twilio LaunchDarkly Audiences destination).
Docs: [Twilio Segment Audiences](https://launchdarkly.com/docs/home/flags/twilio).
