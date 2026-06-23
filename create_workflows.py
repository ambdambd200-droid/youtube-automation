"""
Creates n8n workflows for the VARY daily clip pipeline.
Only daily Shorts workflow — no weekly long-form.
"""
import json
import requests
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from config import N8N_API_KEY, N8N_BASE_URL

HEADERS = {"X-N8N-API-KEY": N8N_API_KEY}


def make_node(id, name, node_type, tv, pos, params):
    return {
        "id": id,
        "name": name,
        "type": node_type,
        "typeVersion": tv,
        "position": pos,
        "parameters": params
    }


def create_daily_workflow():
    """Create the daily YouTube Shorts workflow for VARY."""
    nodes = [
        # Trigger: Daily at 12PM UTC
        make_node("cron", "Daily Trigger", "n8n-nodes-base.scheduleTrigger", 1.1, [250, 300], {
            "rule": {"interval": [{"field": "hours", "hoursInterval": 24}]}
        }),

        # Step 1: Select content
        make_node("s1", "Select Content", "n8n-nodes-base.httpRequest", 4.2, [450, 200], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/select-content",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": []
            },
            "options": {}
        }),

        # Step 2: Download clip
        make_node("s2", "Download Clip", "n8n-nodes-base.httpRequest", 4.2, [650, 200], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/download-clip",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "search_query", "value": "={{ $json.search_query }}"},
                    {"name": "type", "value": "={{ $json.type }}"}
                ]
            },
            "options": {}
        }),

        # Step 3: Edit clip to Shorts
        make_node("s3", "Edit Clip", "n8n-nodes-base.httpRequest", 4.2, [850, 200], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/edit-clip",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "source_path", "value": "={{ $json.path }}"},
                    {"name": "type", "value": "={{ $json.content_type || $node['Select Content'].json.type }}"},
                    {"name": "title", "value": "={{ $json.title }}"}
                ]
            },
            "options": {}
        }),

        # Step 4: Generate SEO metadata
        make_node("s4", "Generate SEO", "n8n-nodes-base.httpRequest", 4.2, [1050, 200], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-seo",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "source_title", "value": "={{ $json.source_title }}"},
                    {"name": "type", "value": "={{ $json.content_type }}"},
                    {"name": "source_url", "value": "={{ $json.source_url }}"}
                ]
            },
            "options": {}
        }),

        # Step 5: Generate thumbnails
        make_node("s5", "Generate Thumbnails", "n8n-nodes-base.httpRequest", 4.2, [1250, 200], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-thumbnail",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "video_path", "value": "={{ $json.path }}"},
                    {"name": "title", "value": "={{ $json.source_title || $node['Generate SEO'].json.title }}"},
                    {"name": "type", "value": "={{ $json.content_type }}"}
                ]
            },
            "options": {}
        }),

        # Step 6: Upload to YouTube
        make_node("s6", "Upload to YouTube", "n8n-nodes-base.httpRequest", 4.2, [1450, 200], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/upload",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "video_path", "value": "={{ $json.path }}"},
                    {"name": "title", "value": "={{ $node['Generate SEO'].json.title }}"},
                    {"name": "description", "value": "={{ $node['Generate SEO'].json.description }}"},
                    {"name": "tags", "value": "={{ $node['Generate SEO'].json.tags }}"},
                    {"name": "thumbnail_path", "value": "={{ Object.values($json.variants)[0] || '' }}"}
                ]
            },
            "options": {}
        }),

        # Step 7: Cleanup
        make_node("s7", "Cleanup Space", "n8n-nodes-base.httpRequest", 4.2, [1650, 200], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/cleanup",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "source_paths", "value": "={{ [$node['Download Clip'].json.path] }}"}
                ]
            },
            "options": {}
        }),
    ]

    connections = {
        "Daily Trigger": {"main": [[{"node": "Select Content", "type": "main", "index": 0}]]},
        "Select Content": {"main": [[{"node": "Download Clip", "type": "main", "index": 0}]]},
        "Download Clip": {"main": [[{"node": "Edit Clip", "type": "main", "index": 0}]]},
        "Edit Clip": {"main": [
            [{"node": "Generate SEO", "type": "main", "index": 0}],
            [{"node": "Generate Thumbnails", "type": "main", "index": 0}]
        ]},
        "Generate SEO": {"main": [[{"node": "Upload to YouTube", "type": "main", "index": 0}]]},
        "Generate Thumbnails": {"main": [[{"node": "Upload to YouTube", "type": "main", "index": 0}]]},
        "Upload to YouTube": {"main": [[{"node": "Cleanup Space", "type": "main", "index": 0}]]},
    }

    return {
        "name": "VARY - Daily Short - Automation",
        "nodes": nodes,
        "connections": connections,
        "settings": {},
        "staticData": None,
        "pinData": {},
        "tags": ["VARY", "daily", "shorts"],
    }


def create_via_api(wf):
    """Create a workflow in n8n via API."""
    url = f"{N8N_BASE_URL}/api/v1/workflows"
    try:
        r = requests.post(url, headers=HEADERS, json=wf, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            print(f"  OK: {data.get('name')} (ID: {data.get('id')})")
            return data
        else:
            print(f"  FAILED ({r.status_code}): {r.text[:200]}")
            return None
    except requests.exceptions.ConnectionError:
        print(f"  FAILED: Cannot connect to n8n at {N8N_BASE_URL}")
        print(f"  Make sure n8n is running.")
        return None
    except Exception as e:
        print(f"  FAILED: {e}")
        return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Creating VARY n8n workflows...")
    print()
    print("[1/1] Daily Short Workflow:")
    create_via_api(create_daily_workflow())
    print()
    print("Done! Check n8n UI at http://localhost:5678")
    print()
    print("NOTE: The old weekly long-form workflow has been removed.")
    print("Only daily Shorts will be created.")
