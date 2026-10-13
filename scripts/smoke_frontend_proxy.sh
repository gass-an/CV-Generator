#!/usr/bin/env bash
set -euo pipefail

web_image="${1:?Indiquez une image frontend à tester}"
mock_backend_image="${2:?Indiquez une image Python pour le backend simulé}"
repository_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
suffix="${GITHUB_RUN_ID:-local}-$$"
network="cv-generator-smoke-$suffix"
backend="cv-generator-smoke-api-$suffix"
frontend="cv-generator-smoke-web-$suffix"
unauthorized_body="/tmp/cv-generator-smoke-401-$suffix.json"
missing_body="/tmp/cv-generator-smoke-404-$suffix.json"
redoc_body="/tmp/cv-generator-smoke-redoc-404-$suffix.html"

cleanup() {
  docker rm --force "$frontend" "$backend" >/dev/null 2>&1 || true
  docker network rm "$network" >/dev/null 2>&1 || true
  rm -f "$unauthorized_body" "$missing_body" "$redoc_body"
}
trap cleanup EXIT

docker network create "$network" >/dev/null
docker run --detach --name "$backend" --network "$network" \
  --network-alias generator-api \
  --mount "type=bind,source=$repository_root/scripts/nginx_smoke_backend.py,target=/smoke_backend.py,readonly" \
  "$mock_backend_image" python /smoke_backend.py >/dev/null
docker run --detach --name "$frontend" --network "$network" \
  --publish 127.0.0.1::80 "$web_image" >/dev/null

host_port=$(docker inspect --format '{{(index (index .NetworkSettings.Ports "80/tcp") 0).HostPort}}' "$frontend")
base_url="http://127.0.0.1:$host_port"

ready=false
for _ in {1..30}; do
  if curl --fail --silent "$base_url/" >/dev/null; then
    ready=true
    break
  fi
  sleep 1
done
test "$ready" = true

for path in / /historique /parametres; do
  curl --fail --silent "$base_url$path" | grep -q '<div id="root"></div>'
done

backend_ready=false
for _ in {1..30}; do
  if curl --fail --silent \
    -H 'X-API-Key: smoke-api-key' \
    "$base_url/api/v1/health" >/dev/null; then
    backend_ready=true
    break
  fi
  sleep 1
done

if [[ "$backend_ready" != "true" ]]; then
  echo "Le backend simulé n'est pas accessible via Nginx."
  exit 1
fi

health_body=$(curl --fail --silent -H 'X-API-Key: smoke-api-key' "$base_url/api/v1/health")
grep -q '"path": "/api/v1/health"' <<<"$health_body"
grep -q '"api_key": "smoke-api-key"' <<<"$health_body"

unauthorized_status=$(curl --silent --output "$unauthorized_body" \
  --write-out '%{http_code}' "$base_url/api/v1/unauthorized")
test "$unauthorized_status" = 401
grep -q '"code": "invalid_api_key"' "$unauthorized_body"
! grep -q '<div id="root"></div>' "$unauthorized_body"

missing_status=$(curl --silent --output "$missing_body" \
  --write-out '%{http_code}' "$base_url/api/v1/missing")
test "$missing_status" = 404
grep -q '"path": "/api/v1/missing"' "$missing_body"
! grep -q '<div id="root"></div>' "$missing_body"

redoc_status=$(curl --silent --output "$redoc_body" \
  --write-out '%{http_code}' "$base_url/redoc")
test "$redoc_status" = 404
! grep -q '<div id="root"></div>' "$redoc_body"

docker exec "$frontend" nginx -t
