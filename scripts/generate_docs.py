#!/usr/bin/env python3
"""
Generate API documentation and export schemas.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any

# Add app to path
sys.path.append(str(Path(__file__).parent.parent))

from app.app_instance import create_app
from app.core.config import settings


def generate_openapi_spec():
    """Generate OpenAPI specification."""
    print("📚 Generating OpenAPI specification...")

    app = create_app()

    # Get OpenAPI schema
    openapi_schema = app.openapi()

    # Enhance schema with additional information
    openapi_schema["info"].update({
        "title": "AI Research Assistant API",
        "description": """
        A comprehensive API for AI-powered academic research assistance.

        ## Features

        - **Paper Management**: Add, organize, and analyze academic papers
        - **AI Analysis**: Automated summarization and insight extraction
        - **Knowledge Base**: Personal research knowledge management
        - **Citation Networks**: Visualize and explore paper relationships
        - **Search**: Semantic search across papers and knowledge

        ## Authentication

        This API uses JWT Bearer token authentication. Include your token in the Authorization header:
        ```
        Authorization: Bearer your-jwt-token
        ```

        ## Rate Limiting

        - Free tier: 100 requests per hour
        - Researcher tier: 1000 requests per hour
        - Institution tier: 10000 requests per hour

        ## Support

        For support, visit our documentation or contact support@airesearch.com
        """,
        "version": settings.version,
        "contact": {
            "name": "AI Research Assistant Support",
            "email": "support@airesearch.com",
            "url": "https://docs.airesearch.com"
        },
        "license": {
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT"
        }
    })

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "http://localhost:8000",
            "description": "Development server"
        },
        {
            "url": "https://api.airesearch.com",
            "description": "Production server"
        }
    ]

    # Add security schemes
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    # Add tags descriptions
    openapi_schema["tags"] = [
        {
            "name": "authentication",
            "description": "User authentication and authorization"
        },
        {
            "name": "users",
            "description": "User profile management"
        },
        {
            "name": "papers",
            "description": "Academic paper management and analysis"
        },
        {
            "name": "knowledge",
            "description": "Personal knowledge base management"
        },
        {
            "name": "search",
            "description": "Search papers and knowledge entries"
        },
        {
            "name": "citations",
            "description": "Citation network analysis"
        },
        {
            "name": "health",
            "description": "System health and monitoring"
        }
    ]

    # Save OpenAPI spec
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)

    with open(docs_dir / "openapi.json", "w") as f:
        json.dump(openapi_schema, f, indent=2)

    print(f"✅ OpenAPI spec saved to {docs_dir / 'openapi.json'}")
    return openapi_schema


def generate_postman_collection(openapi_schema: Dict[str, Any]):
    """Generate Postman collection from OpenAPI spec."""
    print("📮 Generating Postman collection...")

    collection = {
        "info": {
            "name": "AI Research Assistant API",
            "description": openapi_schema["info"]["description"],
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{jwt_token}}",
                    "type": "string"
                }
            ]
        },
        "variable": [
            {
                "key": "base_url",
                "value": "http://localhost:8000",
                "type": "string"
            },
            {
                "key": "jwt_token",
                "value": "",
                "type": "string"
            }
        ],
        "item": []
    }

    # Group endpoints by tags
    endpoints_by_tag = {}

    for path, methods in openapi_schema["paths"].items():
        for method, details in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                tags = details.get("tags", ["default"])
                tag = tags[0] if tags else "default"

                if tag not in endpoints_by_tag:
                    endpoints_by_tag[tag] = []

                endpoints_by_tag[tag].append({
                    "path": path,
                    "method": method.upper(),
                    "details": details
                })

    # Create Postman folders and requests
    for tag, endpoints in endpoints_by_tag.items():
        folder = {
            "name": tag.title(),
            "item": []
        }

        for endpoint in endpoints:
            request = {
                "name": endpoint["details"].get("summary", f"{endpoint['method']} {endpoint['path']}"),
                "request": {
                    "method": endpoint["method"],
                    "header": [],
                    "url": {
                        "raw": "{{base_url}}" + endpoint["path"],
                        "host": ["{{base_url}}"],
                        "path": endpoint["path"].strip("/").split("/")
                    }
                },
                "response": []
            }

            # Add request body for POST/PUT requests
            if endpoint["method"] in ["POST", "PUT", "PATCH"]:
                request_body = endpoint["details"].get("requestBody")
                if request_body:
                    content = request_body.get("content", {})
                    if "application/json" in content:
                        schema = content["application/json"].get("schema", {})
                        if "example" in schema:
                            request["request"]["body"] = {
                                "mode": "raw",
                                "raw": json.dumps(schema["example"], indent=2),
                                "options": {
                                    "raw": {
                                        "language": "json"
                                    }
                                }
                            }
                        request["request"]["header"].append({
                            "key": "Content-Type",
                            "value": "application/json"
                        })

            # Add query parameters
            parameters = endpoint["details"].get("parameters", [])
            query_params = [p for p in parameters if p.get("in") == "query"]
            if query_params:
                request["request"]["url"]["query"] = []
                for param in query_params:
                    request["request"]["url"]["query"].append({
                        "key": param["name"],
                        "value": param.get("example", ""),
                        "description": param.get("description", "")
                    })

            folder["item"].append(request)

        collection["item"].append(folder)

    # Save Postman collection
    docs_dir = Path("docs")
    with open(docs_dir / "postman_collection.json", "w") as f:
        json.dump(collection, f, indent=2)

    print(f"✅ Postman collection saved to {docs_dir / 'postman_collection.json'}")


def generate_api_reference():
    """Generate human-readable API reference."""
    print("📖 Generating API reference...")

    app = create_app()
    openapi_schema = app.openapi()

    markdown_content = []

    # Header
    markdown_content.append("# AI Research Assistant API Reference\n")
    markdown_content.append(f"Version: {openapi_schema['info']['version']}\n")
    markdown_content.append(f"{openapi_schema['info']['description']}\n")

    # Base URL
    markdown_content.append("## Base URL\n")
    markdown_content.append("```")
    markdown_content.append("Development: http://localhost:8000")
    markdown_content.append("Production: https://api.airesearch.com")
    markdown_content.append("```\n")

    # Authentication
    markdown_content.append("## Authentication\n")
    markdown_content.append("All API endpoints require authentication using JWT Bearer tokens:\n")
    markdown_content.append("```http")
    markdown_content.append("Authorization: Bearer your-jwt-token")
    markdown_content.append("```\n")

    # Endpoints by tag
    endpoints_by_tag = {}
    for path, methods in openapi_schema["paths"].items():
        for method, details in methods.items():
            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                tags = details.get("tags", ["default"])
                tag = tags[0] if tags else "default"

                if tag not in endpoints_by_tag:
                    endpoints_by_tag[tag] = []

                endpoints_by_tag[tag].append({
                    "path": path,
                    "method": method.upper(),
                    "details": details
                })

    # Generate documentation for each tag
    for tag, endpoints in endpoints_by_tag.items():
        markdown_content.append(f"## {tag.title()}\n")

        for endpoint in endpoints:
            details = endpoint["details"]

            # Endpoint header
            markdown_content.append(f"### {details.get('summary', endpoint['method'] + ' ' + endpoint['path'])}\n")

            # Method and path
            markdown_content.append(f"```http")
            markdown_content.append(f"{endpoint['method']} {endpoint['path']}")
            markdown_content.append("```\n")

            # Description
            if "description" in details:
                markdown_content.append(f"{details['description']}\n")

            # Parameters
            parameters = details.get("parameters", [])
            if parameters:
                markdown_content.append("#### Parameters\n")
                markdown_content.append("| Name | Type | In | Description | Required |")
                markdown_content.append("|------|------|-------|-------------|----------|")

                for param in parameters:
                    required = "Yes" if param.get("required", False) else "No"
                    param_type = param.get("schema", {}).get("type", "string")
                    markdown_content.append(
                        f"| {param['name']} | {param_type} | {param['in']} | "
                        f"{param.get('description', '')} | {required} |"
                    )
                markdown_content.append("")

            # Request body
            request_body = details.get("requestBody")
            if request_body:
                markdown_content.append("#### Request Body\n")
                content = request_body.get("content", {})
                if "application/json" in content:
                    schema = content["application/json"].get("schema", {})
                    if "example" in schema:
                        markdown_content.append("```json")
                        markdown_content.append(json.dumps(schema["example"], indent=2))
                        markdown_content.append("```\n")

            # Responses
            responses = details.get("responses", {})
            if responses:
                markdown_content.append("#### Responses\n")
                for status_code, response in responses.items():
                    markdown_content.append(f"**{status_code}** - {response.get('description', '')}\n")

            markdown_content.append("---\n")

    # Save API reference
    docs_dir = Path("docs")
    with open(docs_dir / "api_reference.md", "w") as f:
        f.write("\n".join(markdown_content))

    print(f"✅ API reference saved to {docs_dir / 'api_reference.md'}")


def generate_sdk_examples():
    """Generate SDK usage examples."""
    print("💻 Generating SDK examples...")

    examples = {
        "python": {
            "filename": "python_examples.py",
            "content": '''
"""
Python SDK usage examples for AI Research Assistant API.
"""
import requests
import json

class AIResearchClient:
    def __init__(self, base_url="http://localhost:8000", token=None):
        self.base_url = base_url
        self.token = token
        self.session = requests.Session()
        if token:
            self.session.headers.update({"Authorization": f"Bearer {token}"})

    def login(self, email, password):
        """Login and get access token."""
        response = self.session.post(
            f"{self.base_url}/api/v1/auth/login-json",
            json={"email": email, "password": password}
        )
        response.raise_for_status()

        data = response.json()
        self.token = data["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        return data

    def add_paper(self, paper_url):
        """Add a paper from URL."""
        response = self.session.post(
            f"{self.base_url}/api/v1/papers/",
            params={"paper_url": paper_url}
        )
        response.raise_for_status()
        return response.json()

    def get_papers(self, limit=20):
        """Get user's papers."""
        response = self.session.get(
            f"{self.base_url}/api/v1/papers/",
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

    def search_papers(self, query, limit=20):
        """Search papers."""
        response = self.session.post(
            f"{self.base_url}/api/v1/papers/search",
            json={
                "query": query,
                "limit": limit
            }
        )
        response.raise_for_status()
        return response.json()

    def get_paper_summary(self, paper_id):
        """Get AI-generated paper summary."""
        response = self.session.get(
            f"{self.base_url}/api/v1/papers/{paper_id}/summary"
        )
        response.raise_for_status()
        return response.json()

    def create_knowledge_entry(self, title, content, entry_type="note", tags=None):
        """Create a knowledge entry."""
        response = self.session.post(
            f"{self.base_url}/api/v1/knowledge/",
            json={
                "title": title,
                "content": content,
                "entry_type": entry_type,
                "tags": tags or []
            }
        )
        response.raise_for_status()
        return response.json()

# Usage examples
if __name__ == "__main__":
    # Initialize client
    client = AIResearchClient()

    # Login
    client.login("researcher@university.edu", "researcher123")

    # Add a paper
    paper = client.add_paper("https://arxiv.org/abs/1706.03762")
    print(f"Added paper: {paper['title']}")

    # Get paper summary
    summary = client.get_paper_summary(paper["id"])
    print(f"Summary: {summary['summary']['research_question']}")

    # Search papers
    results = client.search_papers("attention mechanism")
    print(f"Found {len(results['papers'])} papers")

    # Create knowledge entry
    entry = client.create_knowledge_entry(
        title="Attention Mechanism Notes",
        content="Key insights about attention mechanisms in transformers...",
        entry_type="note",
        tags=["attention", "transformers"]
    )
    print(f"Created knowledge entry: {entry['id']}")
'''
        },
        "javascript": {
            "filename": "javascript_examples.js",
            "content": '''
/**
 * JavaScript SDK usage examples for AI Research Assistant API.
 */

class AIResearchClient {
    constructor(baseUrl = 'http://localhost:8000', token = null) {
        this.baseUrl = baseUrl;
        this.token = token;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        if (this.token) {
            config.headers.Authorization = `Bearer ${this.token}`;
        }

        const response = await fetch(url, config);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return response.json();
    }

    async login(email, password) {
        const data = await this.request('/api/v1/auth/login-json', {
            method: 'POST',
            body: JSON.stringify({ email, password })
        });

        this.token = data.access_token;
        return data;
    }

    async addPaper(paperUrl) {
        return this.request(`/api/v1/papers/?paper_url=${encodeURIComponent(paperUrl)}`, {
            method: 'POST'
        });
    }

    async getPapers(limit = 20) {
        return this.request(`/api/v1/papers/?limit=${limit}`);
    }

    async searchPapers(query, limit = 20) {
        return this.request('/api/v1/papers/search', {
            method: 'POST',
            body: JSON.stringify({ query, limit })
        });
    }

    async getPaperSummary(paperId) {
        return this.request(`/api/v1/papers/${paperId}/summary`);
    }

    async createKnowledgeEntry(title, content, entryType = 'note', tags = []) {
        return this.request('/api/v1/knowledge/', {
            method: 'POST',
            body: JSON.stringify({
                title,
                content,
                entry_type: entryType,
                tags
            })
        });
    }
}

// Usage examples
async function examples() {
    const client = new AIResearchClient();

    try {
        // Login
        await client.login('researcher@university.edu', 'researcher123');

        // Add a paper
        const paper = await client.addPaper('https://arxiv.org/abs/1706.03762');
        console.log('Added paper:', paper.title);

        // Get paper summary
        const summary = await client.getPaperSummary(paper.id);
        console.log('Summary:', summary.summary.research_question);

        // Search papers
        const results = await client.searchPapers('attention mechanism');
        console.log('Found papers:', results.papers.length);

        // Create knowledge entry
        const entry = await client.createKnowledgeEntry(
            'Attention Mechanism Notes',
            'Key insights about attention mechanisms in transformers...',
            'note',
            ['attention', 'transformers']
        );
        console.log('Created knowledge entry:', entry.id);

    } catch (error) {
        console.error('Error:', error.message);
    }
}

// Run examples
examples();
'''
        }
    }

    docs_dir = Path("docs")
    examples_dir = docs_dir / "examples"
    examples_dir.mkdir(exist_ok=True)

    for lang, example in examples.items():
        with open(examples_dir / example["filename"], "w") as f:
            f.write(example["content"])
        print(f"✅ {lang.title()} examples saved to {examples_dir / example['filename']}")


def generate_changelog():
    """Generate changelog template."""
    print("📝 Generating changelog...")

    changelog_content = """# Changelog

All notable changes to the AI Research Assistant API will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial API release
- User authentication and management
- Paper processing and analysis
- AI-powered summarization
- Knowledge base management
- Citation network analysis
- Semantic search capabilities

### Changed

### Deprecated

### Removed

### Fixed

### Security

## [1.0.0] - 2024-01-01

### Added
- Complete API implementation
- Comprehensive test suite
- Docker containerization
- CI/CD pipeline
- API documentation
- SDK examples

---

## Template for future releases:

## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes in existing functionality

### Deprecated
- Soon-to-be removed features

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security fixes
"""

    docs_dir = Path("docs")
    with open(docs_dir / "CHANGELOG.md", "w") as f:
        f.write(changelog_content)

    print(f"✅ Changelog saved to {docs_dir / 'CHANGELOG.md'}")


def main():
    """Generate all documentation."""
    print("📚 Generating API documentation...\n")

    try:
        # Generate OpenAPI spec
        openapi_schema = generate_openapi_spec()

        # Generate Postman collection
        generate_postman_collection(openapi_schema)

        # Generate API reference
        generate_api_reference()

        # Generate SDK examples
        generate_sdk_examples()

        # Generate changelog
        generate_changelog()

        print("\n🎉 Documentation generation complete!")
        print("\nGenerated files:")
        print("- docs/openapi.json - OpenAPI specification")
        print("- docs/postman_collection.json - Postman collection")
        print("- docs/api_reference.md - Human-readable API reference")
        print("- docs/examples/ - SDK usage examples")
        print("- docs/CHANGELOG.md - Changelog template")

    except Exception as e:
        print(f"❌ Documentation generation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()