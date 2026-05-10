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

def create_short_workflow():
    nodes = [
        make_node("cron", "Daily Trigger", "n8n-nodes-base.scheduleTrigger", 1.1, [250, 300], {
            "rule": {"interval": [{"field": "hours", "hoursInterval": 24}]}
        }),
        make_node("s1", "Generate Script", "n8n-nodes-base.httpRequest", 4.2, [450, 300], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-script",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [{"name": "type", "value": "short"}]
            },
            "options": {}
        }),
        make_node("s2", "Generate Voiceover", "n8n-nodes-base.httpRequest", 4.2, [650, 300], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-tts",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "script", "value": "={{ $json.script }}"},
                    {"name": "output_prefix", "value": "={{ 'short_' + Date.now().toString() }}"}
                ]
            },
            "options": {}
        }),
        make_node("s3", "Fetch Images", "n8n-nodes-base.httpRequest", 4.2, [850, 300], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/fetch-images",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "query", "value": "={{ $json.topic }}"},
                    {"name": "count", "value": 5}
                ]
            },
            "options": {}
        }),
        make_node("s4", "Assemble Video", "n8n-nodes-base.httpRequest", 4.2, [1050, 250], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/assemble-video",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [{"name": "type", "value": "short"}]
            },
            "options": {}
        }),
        make_node("s5", "Generate Thumbnail", "n8n-nodes-base.httpRequest", 4.2, [1050, 500], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-thumbnail",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [{"name": "title", "value": "={{ $json.title }}"}]
            },
            "options": {}
        })
    ]

    connections = {
        "Daily Trigger": {"main": [[{"node": "Generate Script", "type": "main", "index": 0}]]},
        "Generate Script": {"main": [[{"node": "Generate Voiceover", "type": "main", "index": 0}]]},
        "Generate Voiceover": {"main": [[{"node": "Fetch Images", "type": "main", "index": 0}]]},
        "Fetch Images": {"main": [[{"node": "Assemble Video", "type": "main", "index": 0}]]}
    }

    return {
        "name": "YouTube Daily Short - Automation",
        "nodes": nodes,
        "connections": connections,
        "settings": {},
        "staticData": None,
        "pinData": {}
    }

def create_long_workflow():
    nodes = [
        make_node("cron", "Weekly Trigger", "n8n-nodes-base.scheduleTrigger", 1.1, [250, 300], {
            "rule": {"interval": [{"field": "days", "daysInterval": 7}]}
        }),
        make_node("s1", "Generate Script", "n8n-nodes-base.httpRequest", 4.2, [450, 300], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-script",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [{"name": "type", "value": "long"}]
            },
            "options": {}
        }),
        make_node("s2", "Generate Voiceover", "n8n-nodes-base.httpRequest", 4.2, [650, 300], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-tts",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "script", "value": "={{ $json.script }}"},
                    {"name": "output_prefix", "value": "={{ 'long_' + Date.now().toString() }}"}
                ]
            },
            "options": {}
        }),
        make_node("s3", "Fetch Images", "n8n-nodes-base.httpRequest", 4.2, [850, 300], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/fetch-images",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [
                    {"name": "query", "value": "={{ $json.topic }}"},
                    {"name": "count", "value": 10}
                ]
            },
            "options": {}
        }),
        make_node("s4", "Assemble Video", "n8n-nodes-base.httpRequest", 4.2, [1050, 250], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/assemble-video",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [{"name": "type", "value": "long"}]
            },
            "options": {}
        }),
        make_node("s5", "Generate Thumbnail", "n8n-nodes-base.httpRequest", 4.2, [1050, 500], {
            "method": "POST",
            "url": "http://127.0.0.1:5001/generate-thumbnail",
            "authentication": "none",
            "sendBody": True,
            "bodyParameters": {
                "parameters": [{"name": "title", "value": "={{ $json.title }}"}]
            },
            "options": {}
        })
    ]

    connections = {
        "Weekly Trigger": {"main": [[{"node": "Generate Script", "type": "main", "index": 0}]]},
        "Generate Script": {"main": [[{"node": "Generate Voiceover", "type": "main", "index": 0}]]},
        "Generate Voiceover": {"main": [[{"node": "Fetch Images", "type": "main", "index": 0}]]},
        "Fetch Images": {"main": [[{"node": "Assemble Video", "type": "main", "index": 0}]]}
    }

    return {
        "name": "YouTube Weekly Long-Form - Automation",
        "nodes": nodes,
        "connections": connections,
        "settings": {},
        "staticData": None,
        "pinData": {}
    }

def create_via_api(wf):
    url = f"{N8N_BASE_URL}/api/v1/workflows"
    r = requests.post(url, headers=HEADERS, json=wf)
    if r.status_code in (200, 201):
        data = r.json()
        print(f"  OK: {data.get('name')} (ID: {data.get('id')})")
        return data
    else:
        print(f"  FAILED ({r.status_code}): {r.text[:200]}")
        return None

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print("Creating n8n workflows...")
    print()
    print("[1/2] Daily Short Workflow:")
    create_via_api(create_short_workflow())
    print()
    print("[2/2] Weekly Long-Form Workflow:")
    create_via_api(create_long_workflow())
    print()
    print("Done! Check n8n UI at http://localhost:5678")
