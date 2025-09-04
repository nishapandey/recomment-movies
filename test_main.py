import pytest
from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_recommend_seed_movie():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/recommend", json={
            "user_id": "tester",
            "seed_movie": "Inception",
            "num": 2,
            "region": "US"
        })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["movies"]) > 0
    # check movie fields
    movie = data["movies"][0]
    assert "title" in movie
    assert "providers" in movie


@pytest.mark.asyncio
async def test_recommend_query():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/recommend", json={
            "user_id": "tester",
            "query": "Batman",
            "num": 2,
            "region": "US"
        })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["movies"]) > 0


@pytest.mark.asyncio
async def test_recommend_genre():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/recommend", json={
            "user_id": "tester",
            "genre": "action",
            "num": 3,
            "region": "US"
        })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert len(data["movies"]) > 0
