import os

project_name = "land-encroachment-project"

folders = [
    f"{project_name}/frontend/css",
    f"{project_name}/frontend/js",
    f"{project_name}/frontend/assets/images",
    f"{project_name}/backend/data",
    f"{project_name}/backend/api",
    f"{project_name}/ml",
    f"{project_name}/datasets",
    f"{project_name}/docs"
]

files = {
    f"{project_name}/frontend/index.html": "<h1>Land Encroachment Dashboard</h1>",
    f"{project_name}/frontend/css/style.css": "body { font-family: Arial; }",
    f"{project_name}/frontend/js/app.js": "console.log('Dashboard loaded');",
    f"{project_name}/backend/app.py": "# Backend entry point",
    f"{project_name}/backend/config.py": "# Configuration file",
    f"{project_name}/ml/model.py": "# ML model code",
    f"{project_name}/README.md": "# Land Encroachment Monitoring System"
}

# Create folders
for folder in folders:
    os.makedirs(folder, exist_ok=True)

# Create files
for path, content in files.items():
    with open(path, "w") as f:
        f.write(content)

print("✅ Project folders and files created successfully!")
