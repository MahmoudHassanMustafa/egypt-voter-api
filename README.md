# Egypt Voter API

REST API for querying Egyptian electoral/voter information by national ID with automatic retry mechanism and comprehensive error handling.

---

## 🚀 Features

- ✅ **14-Digit National ID Validation** - Strict validation with clear error messages
- ✅ **Automatic Retry Mechanism** - Up to 3 attempts with exponential backoff
- ✅ **District Filtering** - Filter by target electoral districts
- ✅ **Comprehensive Error Handling** - All edge cases covered
- ✅ **Clean JSON Responses** - User-friendly, consistent format
- ✅ **Interactive Documentation** - Built-in Swagger UI
- ✅ **Headless Browser** - Runs in background without GUI
- ✅ **CORS Enabled** - Ready for cross-origin requests

---

## 📋 Quick Start

### Option 1: Using Docker (Recommended) 🐳

```bash
# Build and start the container
docker-compose up -d

# Test the API
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "29710260300314"}'
```

**That's it!** The API is now running in Docker.

### Option 2: Running Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the API
python api.py

# 3. Test it
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "29710260300314"}'
```

The API will be available at: **http://localhost:8000**

---

## 🐳 Docker Deployment

### Quick Start with Docker

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Docker Commands

| Command | Description |
|---------|-------------|
| `docker-compose up -d` | Start in background |
| `docker-compose down` | Stop and remove containers |
| `docker-compose logs -f` | View logs (live) |
| `docker-compose restart` | Restart containers |
| `docker-compose ps` | Check status |
| `docker-compose exec egypt-voter-api bash` | Open shell in container |
| `docker-compose up -d --build` | Rebuild and restart |

### Development Mode (with hot reload)

```bash
# Use development compose file
docker-compose -f docker-compose.dev.yml up

# Changes to api.py or selenium_scraper.py will auto-reload
```

### Docker Configuration

**Resource Limits** (edit `docker-compose.yml`):
```yaml
resources:
  limits:
    cpus: '2'      # Max CPU cores
    memory: 2G     # Max RAM
```

**Environment Variables**:
```yaml
environment:
  - DD_TRACE_ENABLED=false
  - MAX_RETRIES=3
  - RETRY_DELAY=2
```

**Port Mapping**:
```yaml
ports:
  - "8080:8000"  # host:container
```

### Using the Build Script

```bash
# Automated build and deployment
./scripts/build-and-run.sh
```

The script will:
- Check Docker installation
- Stop existing containers
- Build the image
- Start the container
- Verify health
- Show access URLs

---

## 📖 Documentation

### Interactive API Docs
- **Swagger UI**: http://localhost:8000/docs - Full API documentation with live testing
- **ReDoc**: http://localhost:8000/redoc - Alternative API documentation

---

## 🎯 API Endpoints

### `POST /lookup`

Query electoral data by national ID.

**Request:**
```json
{
  "national_id": "29710260300314"
}
```

**Response (Registered):**
```json
{
  "success": true,
  "national_id": "29710260300314",
  "status": "registered",
  "data": {
    "electoral_center": "مدرسه التربيه الفكريه الاساسيه المشتركة",
    "district": "قسم الشرق",
    "address": "مساكن بلال بن رباح",
    "subcommittee_number": "20",
    "electoral_list_number": "7881"
  }
}
```

**Response (Validation Error):**
```json
{
  "success": false,
  "error": "National ID must be exactly 14 digits, got 13 characters",
  "field": "national_id",
  "input": "2971026000314"
}
```

---

## 🔄 Retry Mechanism

The API automatically retries failed requests up to **3 times** with exponential backoff:

- **Attempt 1**: Immediate
- **Attempt 2**: Wait 2 seconds
- **Attempt 3**: Wait 4 seconds
- **Total**: ~14 seconds before giving up

### Retries Happen For:
- Network connection issues
- Timeout errors
- Page loading failures
- Temporary website unavailability

### NO Retries For:
- Invalid national ID format (validation errors)
- Person not registered (valid response)
- Person underage (valid response)

---

## 📊 All Response Types

| Status | HTTP Code | Retries? | Description |
|--------|-----------|----------|-------------|
| `registered` | 200 | ❌ | Voter found in target district |
| `out_of_district` | 200 | ❌ | Voter found but outside target |
| `not_registered` | 200 | ❌ | Not in voter database |
| `underage` | 200 | ❌ | Below voting age |
| Validation error | 400 | ❌ | Invalid national ID format |
| Retries exhausted | 200 | ✅ | Failed after 3 attempts |
| Service unavailable | 503 | ❌ | Scraper not initialized |

---

## 🎯 Target Districts

The API only returns full data for voters in these districts:

- قسم الشرق
- قسم العرب
- قسم الضواحى
- قسم أول بورفؤاد
- قسم ثان بورفؤاد

Voters in other districts receive `status: "out_of_district"` with basic info only.

---

## 💻 Usage Examples

### Python

```python
import requests

response = requests.post(
    "http://localhost:8000/lookup",
    json={"national_id": "29710260300314"}
)

data = response.json()

if data["success"]:
    if data["status"] == "registered":
        print(f"✅ Registered in {data['data']['district']}")
        print(f"Subcommittee: {data['data']['subcommittee_number']}")
    elif data["status"] == "out_of_district":
        print(f"⚠️ Outside target: {data['data']['district']}")
    elif data["status"] == "not_registered":
        print("❌ Not registered")
    elif data["status"] == "underage":
        print("❌ Underage")
else:
    print(f"❌ Error: {data['error']}")
```

### JavaScript

```javascript
const response = await fetch('http://localhost:8000/lookup', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({national_id: '29710260300314'})
});

const data = await response.json();

if (data.success) {
  switch(data.status) {
    case 'registered':
      console.log('✅ Registered:', data.data);
      break;
    case 'out_of_district':
      console.log('⚠️ Outside target:', data.data.district);
      break;
    case 'not_registered':
      console.log('❌ Not registered');
      break;
    case 'underage':
      console.log('❌ Underage');
      break;
  }
} else {
  console.error('❌ Error:', data.error);
}
```

### cURL

```bash
# Valid request
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "29710260300314"}'

# Invalid format
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "123"}'
```

---

## ⚙️ Configuration

### Modify Retry Settings

Edit `api.py`:

```python
scraper = FreeElectionsScraper(
    headless=True,
    max_retries=5,      # Increase retries
    retry_delay=3       # Increase base delay
)
```

### Change Target Districts

Edit `api.py`:

```python
ALLOWED_DISTRICTS = [
    "قسم الشرق",
    "قسم العرب",
    # Add or remove districts
]
```

### Change Port

```bash
# Command line
uvicorn api:app --host 0.0.0.0 --port 8080

# Or edit api.py
uvicorn.run("api:app", host="0.0.0.0", port=8080)
```

---

## 🧪 Testing

### Quick Test

```bash
# Start API
python api.py

# Test in another terminal
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "29710260300314"}'
```

### Run Test Suite

```bash
# Run tests (create test_all_cases.py with your test cases)
python test_all_cases.py

# Or test manually
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "29710260300314"}'
```

---

## 📁 Project Structure

```
egypt-voter-api/
├── api.py                   # FastAPI application (REST API)
├── selenium_scraper.py      # Core scraping engine
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker image definition
├── docker-compose.yml      # Docker Compose (production)
├── docker-compose.dev.yml  # Docker Compose (development)
├── .dockerignore           # Docker build exclusions
├── scripts/                # Utility scripts
│   ├── start_api.sh       # Local startup script
│   └── build-and-run.sh   # Docker build and run script
└── README.md              # This file
```

---

## 🔧 Requirements

### For Docker Deployment (Recommended)
- **Docker** 20.10+
- **Docker Compose** 2.0+
- **2GB RAM** minimum (4GB recommended)
- **Internet Connection**

### For Local Deployment
- **Python 3.8+**
- **Chrome Browser** (for Selenium)
- **ChromeDriver** (automatically managed by webdriver-manager)
- **Internet Connection**

### Python Packages (if running locally)

```
pandas>=2.0.0
openpyxl>=3.1.0
selenium>=4.15.0
webdriver-manager>=4.0.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
pydantic>=2.0.0
```

---

## 🛠️ Troubleshooting

### ChromeDriver Issues

If you get ChromeDriver errors:

1. Make sure Chrome browser is installed
2. `webdriver-manager` should automatically download ChromeDriver
3. If issues persist, manually install ChromeDriver from https://chromedriver.chromium.org/

### Port Already in Use

```bash
# Using Python directly
uvicorn api:app --host 0.0.0.0 --port 8080

# Using Docker - edit docker-compose.yml
ports:
  - "8080:8000"  # Change to desired port
```

### Service Unavailable (503)

**Local deployment:**
```bash
# Stop (Ctrl+C) and restart
python api.py
```

**Docker deployment:**
```bash
# Check logs
docker-compose logs -f

# Restart
docker-compose restart

# Rebuild if needed
docker-compose down
docker-compose up -d --build
```

### Container Issues (Docker)

```bash
# Check container status
docker ps

# Check logs
docker-compose logs egypt-voter-api

# Increase memory (edit docker-compose.yml)
memory: 4G

# Increase shared memory
shm_size: 4gb
```

---

## 📝 API Response Format

All responses follow a consistent format:

### Success Response
```json
{
  "success": true,
  "national_id": "...",
  "status": "registered|out_of_district|not_registered|underage",
  "data": { ... }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message",
  "field": "field_name",        // For validation errors
  "input": "invalid_value",     // For validation errors
  "retries_exhausted": true     // If all retries failed
}
```

---

## 🔐 Security Considerations

### For Production Use:

1. **Configure CORS properly** - Don't allow all origins
   ```python
   allow_origins=["https://yourdomain.com"]
   ```

2. **Add rate limiting** - Prevent abuse
   ```bash
   pip install slowapi
   ```

3. **Add authentication** - Protect the API
   ```bash
   pip install python-jose[cryptography]
   ```

4. **Use HTTPS** - Encrypt traffic

5. **Monitor logs** - Track usage and errors

---

## 📞 Support

For issues or questions:

1. Check the **API documentation** at http://localhost:8000/docs
2. View **logs** in the terminal for detailed error information
3. Check **container logs** if using Docker: `docker-compose logs -f`
4. Review the response format and status codes in this README

---

## 🎉 Features Summary

✅ **Robust** - Automatic retries with exponential backoff  
✅ **Reliable** - All edge cases handled  
✅ **Fast** - Concurrent requests supported  
✅ **Clean** - User-friendly error messages  
✅ **Dockerized** - Easy deployment with Docker  
✅ **Secure** - Non-root user, resource limits, health checks  
✅ **Production-Ready** - Error handling and logging built-in  

---

## 📄 License

This project is provided as-is for electoral data verification purposes.

---

## 🚀 Getting Started in 3 Steps

### Using Docker (Recommended)

```bash
# 1. Run with Docker
docker-compose up -d

# 2. Check health
curl http://localhost:8000/health

# 3. Test the API
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "29710260300314"}'
```

**That's it! The API is now ready to use.** 🎉

### Using Local Python

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the API
python api.py

# 3. Test
curl -X POST "http://localhost:8000/lookup" \
  -H "Content-Type: application/json" \
  -d '{"national_id": "29710260300314"}'
```
