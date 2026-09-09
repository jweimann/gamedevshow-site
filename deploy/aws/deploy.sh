#!/usr/bin/env bash
#
# Publish gamedev.show to S3 behind CloudFront, the same shape as aidevshow.com.
#
#     bash deploy/aws/deploy.sh gamedev.show
#
# NOTHING HERE HAS BEEN RUN. Every step needs AWS credentials, which are Jason's to
# provide with `aws configure` and are never typed into an agent session. Run it
# yourself, or read it and run the steps by hand - it is written step by step for
# exactly that reason.
#
# It is safe to re-run: every step checks for what it would create before creating it,
# so a second run after a failure picks up where the first stopped rather than making a
# second bucket or a second distribution.

set -euo pipefail

DOMAIN="${1:-gamedev.show}"
REGION="us-east-1"          # CloudFront certificates must live here
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SITE="$ROOT/site"

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
need() { command -v "$1" >/dev/null || { echo "missing: $1"; exit 1; }; }

need aws
[ -f "$SITE/index.html" ] || { echo "no site/index.html - run build_site.py first"; exit 1; }

aws sts get-caller-identity >/dev/null || {
  echo "AWS credentials are not configured. Run: aws configure"; exit 1; }

# ---------------------------------------------------------------- 1. the bucket
step "Bucket s3://$DOMAIN"
if aws s3api head-bucket --bucket "$DOMAIN" 2>/dev/null; then
  echo "already exists"
else
  aws s3api create-bucket --bucket "$DOMAIN" --region "$REGION"
  echo "created"
fi

# The bucket stays private; CloudFront reads it through an Origin Access Control. That
# is why there is no website-hosting configuration and no public bucket policy here.
aws s3api put-public-access-block --bucket "$DOMAIN" \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# ---------------------------------------------------------------- 2. the certificate
step "Certificate for $DOMAIN and www.$DOMAIN"
CERT_ARN="$(aws acm list-certificates --region "$REGION" \
  --query "CertificateSummaryList[?DomainName=='$DOMAIN'].CertificateArn | [0]" --output text)"

if [ "$CERT_ARN" = "None" ] || [ -z "$CERT_ARN" ]; then
  CERT_ARN="$(aws acm request-certificate --region "$REGION" \
    --domain-name "$DOMAIN" --subject-alternative-names "www.$DOMAIN" \
    --validation-method DNS --query CertificateArn --output text)"
  echo "requested $CERT_ARN"
  sleep 10   # ACM needs a moment before the validation record is readable
fi

step "ADD THIS CNAME AT NAMECHEAP, then wait for the certificate to go ISSUED"
aws acm describe-certificate --region "$REGION" --certificate-arn "$CERT_ARN" \
  --query "Certificate.DomainValidationOptions[].ResourceRecord" --output table

echo
echo "Namecheap: Domain List -> $DOMAIN -> Advanced DNS -> Add New Record."
echo "Host is the name above WITHOUT the trailing .$DOMAIN part; value is as shown."
echo "Waiting for validation (Ctrl-C is safe; re-run this script to resume)..."
aws acm wait certificate-validated --region "$REGION" --certificate-arn "$CERT_ARN"
echo "certificate issued"

# ---------------------------------------------------------------- 3. the distribution
step "CloudFront distribution"
DIST_ID="$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, '$DOMAIN')].Id | [0]" \
  --output text 2>/dev/null || echo None)"

if [ "$DIST_ID" = "None" ] || [ -z "$DIST_ID" ]; then
  echo "Creating the distribution needs a config document; this script stops here so the"
  echo "settings are chosen deliberately rather than by a default nobody read."
  echo
  echo "In the console: CloudFront -> Create distribution"
  echo "  Origin              : $DOMAIN.s3.$REGION.amazonaws.com"
  echo "  Origin access       : Origin access control (create one, then COPY the bucket"
  echo "                        policy it offers and apply it to the bucket)"
  echo "  Viewer protocol     : Redirect HTTP to HTTPS"
  echo "  Default root object : index.html"
  echo "  Alternate domains   : $DOMAIN and www.$DOMAIN"
  echo "  Certificate         : $CERT_ARN"
  echo
  echo "Then re-run this script to sync and to print the DNS records."
  exit 0
fi

DIST_DOMAIN="$(aws cloudfront get-distribution --id "$DIST_ID" \
  --query Distribution.DomainName --output text)"
echo "distribution $DIST_ID at $DIST_DOMAIN"

# ---------------------------------------------------------------- 4. upload
step "Sync site/ to s3://$DOMAIN"
# Long cache on the per-episode pages and assets, short on the index so a rebuild shows
# up without waiting for a cache to expire.
aws s3 sync "$SITE" "s3://$DOMAIN" --delete \
  --cache-control "public,max-age=3600" --exclude "index.html"
aws s3 cp "$SITE/index.html" "s3://$DOMAIN/index.html" \
  --cache-control "public,max-age=300"

step "Invalidate the cache"
aws cloudfront create-invalidation --distribution-id "$DIST_ID" --paths '/*' \
  --query 'Invalidation.Id' --output text

# ---------------------------------------------------------------- 5. final DNS
step "FINISH AT NAMECHEAP: Advanced DNS for $DOMAIN"
cat <<EOF

  Type    Host   Value                      TTL
  ALIAS   @      $DIST_DOMAIN   Automatic
  CNAME   www    $DIST_DOMAIN   Automatic

Namecheap BasicDNS supports ALIAS at the apex, which is what lets the bare domain work
without moving DNS to Route 53. Leave the ACM validation CNAME in place - removing it
can cause the certificate to fail renewal.

Then: https://$DOMAIN
EOF
