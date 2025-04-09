#!/bin/bash
secretsmanager () {
    aws --region="us-west-2" secretsmanager get-secret-value --secret-id=""$1"" | jq -r ".SecretString | fromjson | ."$2""
}

# write out a .env file, that will be consumed by the docker-compose
# file in this repo. See `env-file: .env` statement in the docker-compose.
touch .env
{  
 # Server Env Variables
  printf "ENV=%s\n" "production"
  printf "MODE=%s\n" "web"
  printf "NEW_RELIC_KEY=%s\n" "78fc3793d319c8e3bb9d6ee4f4c538fcFFFFNRAL"
  printf "ADMIN_SECRET=%s\n" "$(secretsmanager prod/rocketdevs HASURA_GRAPHQL_ADMIN_SECRET)"
  printf "JWT_SIGNING_KEY=%s\n" "$(secretsmanager prod/rocketdevs ROCKETDEVS_JWT_SIGNING_KEY)"
  printf "HASURA_ENDPOINT=%s\n" "https://talent1.app/hasura/v1/graphql"
  printf "LARK_ERROR_WEBHOOK_URL=%s\n" "https://open.larksuite.com/open-apis/bot/v2/hook/3015b239-4fc4-4033-8e5a-63efe60c42ec"
  printf "OPENAI_API_KEY=%s\n" "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"
} > .env
