# main.py
import os
import asyncio
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
import httpx
from dotenv import load_dotenv


load_dotenv()
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
WATCH_REGION_DEFAULT = os.getenv("WATCH_REGION", "US")
if not TMDB_API_KEY:
    raise RuntimeError("Please set TMDB_API_KEY in .env")

TMDB_BASE = "https://api.themoviedb.org/3"

app = FastAPI(title="Agentic Movie Recommender (MCP/A2A/ACP demo)")

# -------------------------
# Simple A2A Bus (in-process)
# -------------------------


class AgentBus:
    def __init__(self):
        self.agents: Dict[str, Any] = {}

    def register(self, name: str, agent: Any):
        self.agents[name] = agent

    async def send(self, to: str, message: Dict[str, Any]) -> Dict[str, Any]:
        agent = self.agents.get(to)
        if not agent:
            raise RuntimeError(f"Agent '{to}' not registered")
        return await agent.handle(message)

# -------------------------
# MCPClient: wraps TMDb API
# -------------------------


class MCPClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=10.0)

    async def _get(self, path: str, params: Dict[str, Any] = None):
        params = params or {}
        params["api_key"] = self.api_key
        url = f"{TMDB_BASE}{path}"
        r = await self.client.get(url, params=params)
        r.raise_for_status()
        return r.json()

    async def search_movie(self, query: str, page: int = 1):
        return await self._get("/search/movie", {"query": query, "page": page})

    async def get_movie_details(self, movie_id: int):
        return await self._get(f"/movie/{movie_id}")

    async def get_similar(self, movie_id: int, page: int = 1):
        return await self._get(f"/movie/{movie_id}/similar", {"page": page})

    async def discover_by_genres(self, with_genres: str, sort_by: str = "popularity.desc", page: int = 1):
        return await self._get("/discover/movie", {"with_genres": with_genres, "sort_by": sort_by, "page": page})

    async def get_watch_providers(self, movie_id: int):
        # returns a structure with keys per country
        return await self._get(f"/movie/{movie_id}/watch/providers")

    async def get_genre_map(self):
        data = await self._get("/genre/movie/list")
        return {g["name"].lower(): g["id"] for g in data.get("genres", [])}

    async def close(self):
        await self.client.aclose()

# -------------------------
# Agent base
# -------------------------


class Agent:
    def __init__(self, name: str, bus: AgentBus, mcp: MCPClient):
        self.name = name
        self.bus = bus
        self.mcp = mcp

    async def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

# -------------------------
# UserIntentAgent
# - parse incoming client requests -> normalized intent
# - supports seed_movie OR genres OR a free-text query
# -------------------------


class UserIntentAgent(Agent):
    async def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        # ACP-like structured message: {intent: {...}, meta: {...}}
        seed_movie = message.get("seed_movie")
        genre = message.get("genre")
        query = message.get("query")
        num = int(message.get("num", 5))
        region = message.get("region", WATCH_REGION_DEFAULT)

        intent = {"num": num, "region": region}
        if seed_movie:
            # return an intent that says: "find similar to seed_movie"
            intent.update({"type": "seed_movie", "seed_movie": seed_movie})
        elif genre:
            intent.update({"type": "genre", "genre": genre})
        elif query:
            intent.update({"type": "query", "query": query})
        else:
            intent.update({"type": "popular"})

        return {"status": "ok", "intent": intent}

# -------------------------
# RecommenderAgent
# - receives intent and returns list of candidate movies
# -------------------------


class RecommenderAgent(Agent):
    async def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        intent = message.get("intent", {})
        typ = intent.get("type")
        num = intent.get("num", 5)

        if typ == "seed_movie":
            seed = intent.get("seed_movie")
            # find movie id
            search = await self.mcp.search_movie(seed)
            results = search.get("results", [])
            if not results:
                return {"status": "error", "reason": "seed movie not found"}
            movie_id = results[0]["id"]
            similar = await self.mcp.get_similar(movie_id, page=1)
            items = similar.get("results", [])[:num]
        elif typ == "genre":
            # map genre name -> id
            genre_name = intent.get("genre", "").lower()
            genre_map = await self.mcp.get_genre_map()
            genre_id = genre_map.get(genre_name)
            if not genre_id:
                return {"status": "error", "reason": f"unknown genre '{genre_name}'"}
            discover = await self.mcp.discover_by_genres(str(genre_id), page=1)
            items = discover.get("results", [])[:num]
        elif typ == "query":
            q = intent.get("query")
            search = await self.mcp.search_movie(q)
            items = search.get("results", [])[:num]
        else:
            # fallback: popular (discover by popularity)
            discover = await self.mcp.discover_by_genres("", sort_by="popularity.desc", page=1)
            items = discover.get("results", [])[:num]

        # normalize to a compact movie descriptor
        movies = []
        for it in items:
            movies.append({
                "id": it.get("id"),
                "title": it.get("title"),
                "overview": it.get("overview"),
                "release_date": it.get("release_date"),
                "popularity": it.get("popularity"),
            })
        return {"status": "ok", "movies": movies}

# -------------------------
# AvailabilityAgent
# - given movie_id + region returns watch providers
# - uses MCPClient.get_watch_providers
# -------------------------


class AvailabilityAgent(Agent):
    async def handle(self, message: Dict[str, Any]) -> Dict[str, Any]:
        movie_id = message.get("movie_id")
        region = message.get("region", WATCH_REGION_DEFAULT)
        if not movie_id:
            return {"status": "error", "reason": "missing movie_id"}
        wp = await self.mcp.get_watch_providers(movie_id)
        country_info = wp.get("results", {}).get(region)
        if not country_info:
            return {"status": "ok", "providers": []}
        # TMDb returns keys like 'flatrate', 'rent', 'buy' with provider lists
        providers = {}
        for k in ("flatrate", "rent", "buy"):
            lst = country_info.get(k) or []
            providers[k] = [{"provider_id": p["provider_id"], "provider_name": p["provider_name"],
                             "display_priority": p.get("display_priority")} for p in lst]
        return {"status": "ok", "providers": providers}


# -------------------------
# Bootstrapping bus, MCP, agents
# -------------------------
bus = AgentBus()
mcp = MCPClient(TMDB_API_KEY)

user_intent_agent = UserIntentAgent("UserIntentAgent", bus, mcp)
recommender_agent = RecommenderAgent("RecommenderAgent", bus, mcp)
availability_agent = AvailabilityAgent("AvailabilityAgent", bus, mcp)

bus.register("UserIntentAgent", user_intent_agent)
bus.register("RecommenderAgent", recommender_agent)
bus.register("AvailabilityAgent", availability_agent)

# -------------------------
# API models and endpoints
# -------------------------


class RecommendRequest(BaseModel):
    user_id: str
    seed_movie: Optional[str] = None
    genre: Optional[str] = None
    query: Optional[str] = None
    num: Optional[int] = 5
    region: Optional[str] = WATCH_REGION_DEFAULT


class ProviderInfo(BaseModel):
    flatrate: List[Dict[str, Any]] = []
    rent: List[Dict[str, Any]] = []
    buy: List[Dict[str, Any]] = []


class MovieItem(BaseModel):
    id: int
    title: str
    overview: Optional[str]
    release_date: Optional[str]
    popularity: Optional[float]
    providers: Optional[ProviderInfo] = ProviderInfo()


class RecommendResponse(BaseModel):
    status: str
    movies: List[MovieItem]


@app.post("/recommend", response_model=RecommendResponse)
async def recommend(req: RecommendRequest):
    # 1. UserIntentAgent
    intent_msg = {"seed_movie": req.seed_movie, "genre": req.genre,
                  "query": req.query, "num": req.num, "region": req.region}
    intent_resp = await bus.send("UserIntentAgent", intent_msg)
    if intent_resp.get("status") != "ok":
        raise HTTPException(status_code=400, detail="bad intent")
    intent = intent_resp["intent"]

    # 2. RecommenderAgent
    rec_resp = await bus.send("RecommenderAgent", {"intent": intent})
    if rec_resp.get("status") != "ok":
        raise HTTPException(status_code=400, detail=rec_resp.get(
            "reason", "recommendation failed"))
    movies = rec_resp["movies"]

    # 3. For each movie, ask AvailabilityAgent via A2A
    async def enrich(m):
        prov = await bus.send("AvailabilityAgent", {"movie_id": m["id"], "region": req.region})
        providers = prov.get("providers", {})
        # normalize to our MovieItem
        return MovieItem(
            id=m["id"],
            title=m.get("title"),
            overview=m.get("overview"),
            release_date=m.get("release_date"),
            popularity=m.get("popularity"),
            providers=providers
        )
    tasks = [enrich(m) for m in movies]
    enriched = await asyncio.gather(*tasks)
    return {"status": "ok", "movies": enriched}


@app.post("/where_to_watch")
async def where_to_watch(movie_id: int, region: Optional[str] = WATCH_REGION_DEFAULT):
    # direct call to AvailabilityAgent
    resp = await bus.send("AvailabilityAgent", {"movie_id": movie_id, "region": region})
    if resp.get("status") != "ok":
        raise HTTPException(
            status_code=400, detail=resp.get("reason", "failed"))
    return resp


@app.on_event("shutdown")
async def shutdown_event():
    await mcp.close()
