#!/bin/bash

echo "=== Test 1: Query 'Batman' ==="
curl -s -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "np",
        "query": "Batman",
        "num": 2,
        "region": "US"
      }' | jq .
echo -e "\n"

echo "=== Test 2: Seed Movie 'Inception' ==="
curl -s -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "np",
        "seed_movie": "Inception",
        "num": 3,
        "region": "US"
      }' | jq .
echo -e "\n"

echo "=== Test 3: Genre 'action' ==="
curl -s -X POST "http://localhost:8000/recommend" \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": "np",
        "genre": "action",
        "num": 2,
        "region": "US"
      }' | jq .
echo -e "\n"
