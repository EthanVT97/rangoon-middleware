Rangoon Middleware

🚀 Advanced Excel Import with Custom Mapping & ERP Integration

A powerful middleware solution that enables custom Excel file imports with automated ERP system integration. Designed for businesses that need flexible data mapping between POS systems and enterprise ERP platforms.

---

✨ Key Features

🎛️ Custom Column Mapping

· Drag & Drop Interface - Intuitive web-based mapping configuration
· Flexible Field Mapping - Map any Excel column to any ERP field
· Data Transformations - Apply transformations (uppercase, trim, phone format, etc.)
· Validation Rules - Define required fields and data validation rules

📊 Excel Import Capabilities

· Multiple Formats - Support for .xlsx, .xls, and .csv files
· Large File Handling - Process files up to 50MB with background job processing
· Data Validation - Real-time validation with detailed error reporting
· Batch Processing - Handle thousands of records efficiently

🔗 ERP Integration

· REST API Integration - Seamless connection to any ERP system
· Multiple Endpoints - Support for customers, products, sales, and inventory APIs
· Authentication Support - API keys, OAuth, and token-based authentication
· Error Handling - Automatic retry with exponential backoff

📈 Dashboard & Monitoring

· Real-time Job Tracking - Monitor import progress and status
· Error Reporting - Detailed error logs with row-level debugging
· Performance Metrics - Track processing times and success rates
· Upload History - Complete audit trail of all imports

---

🛠️ Technology Stack

Backend

· FastAPI - Modern, fast web framework for APIs
· Python 3.11 - High-performance programming language
· SQLAlchemy - SQL toolkit and ORM
· Pandas - Data analysis and manipulation library

Frontend

· HTML5/CSS3 - Responsive web interface
· JavaScript - Interactive dashboard functionality
· Jinja2 - Templating engine

Deployment

· Render - Cloud platform for deployment
· SQLite - Lightweight database (can upgrade to PostgreSQL)
· Docker - Containerization support

---

🚀 Quick Start

Prerequisites

· Python 3.11+
· Git
· Render account (for deployment)

Local Development

1. Clone Repository
   ```bash
   git clone https://github.com/your-username/pos-erp-middleware.git
   cd pos-erp-middleware
   ```
2. Install Dependencies
   ```bash
   pip install -r requirements.txt
   ```
3. Run Application
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. Access Application
   · Dashboard: http://localhost:8000
   · API Documentation: http://localhost:8000/docs

Production Deployment

1. Deploy on Render
   · Connect your GitHub repository to Render
   · Use the provided render.yaml configuration
   · Auto-deploy on git push
2. Environment Variables
   ```env
   DATABASE_URL=sqlite:///./middleware.db
   ERP_BASE_URL=https://your-erp-system.com/api
   ERP_API_KEY=your-api-key-here
   ```

---

📖 Usage Guide

Step 1: Configure ERP Connection

1. Navigate to Dashboard → ERP Configuration
2. Enter ERP API details:
   · Base URL
   · API Key
   · Endpoint mappings

Step 2: Create Column Mapping

1. Click "Create New Mapping"
2. Define source Excel columns:
   · Column names and data types
   · Required field settings
3. Map to target ERP fields:
   · Field mappings
   · Data transformations
   · Default values

Step 3: Import Excel Files

1. Select your mapping configuration
2. Upload Excel/CSV file
3. Monitor real-time processing
4. Review results and errors

Supported Excel Format

```csv
Profile_ID,Customer_Name,Mobile_Number,Email,Nationality
47290,"John Doe",912345678,john@email.com,US
47291,"Jane Smith",912345679,jane@email.com,UK
```

---

🔌 API Endpoints

Core Endpoints

· GET / - Dashboard interface
· POST /api/import - Import Excel file with mapping
· GET /api/jobs/{job_id} - Get job status
· POST /api/mappings - Create column mapping
· GET /api/mappings - List all mappings

ERP Integration

· POST /api/erp/connection - Configure ERP connection
· GET /api/erp/test - Test ERP connection
· POST /api/erp/sync - Manual sync trigger

Monitoring

· GET /api/system-status - System health check
· GET /api/upload-history - Import history
· GET /api/metrics - Performance metrics

---

🗂️ Project Structure

```
pos-erp-middleware/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── models.py              # Data models & Pydantic schemas
│   ├── database.py            # Database configuration
│   ├── erp_integration.py     # ERP API communication
│   └── utils/
│       ├── file_processor.py  # Excel/CSV processing
│       ├── validators.py      # Data validation
│       └── mapping_engine.py  # Column mapping logic
├── templates/                 # HTML templates
├── static/                   # CSS, JavaScript, assets
├── tests/                    # Test suites
├── requirements.txt          # Python dependencies
├── render.yaml              # Render deployment config
└── README.md               # This file
```

---

🔧 Configuration

Column Mapping Example

```json
{
  "mapping_name": "Customer Import",
  "source_columns": [
    {"name": "Customer_ID", "type": "string", "required": true},
    {"name": "Full_Name", "type": "string", "required": true},
    {"name": "Phone", "type": "string", "required": false}
  ],
  "target_columns": {
    "customer_code": {
      "source_column": "Customer_ID",
      "transformation": "uppercase",
      "required": true
    },
    "customer_name": {
      "source_column": "Full_Name", 
      "transformation": "trim",
      "required": true
    }
  }
}
```

ERP Connection Configuration

```json
{
  "name": "My ERP System",
  "base_url": "https://erp.company.com/api/v1",
  "api_key": "your-secret-api-key",
  "endpoints": {
    "customers": "/customers/batch",
    "products": "/products/batch",
    "sales": "/sales/invoices"
  }
}
```

---

🐛 Troubleshooting

Common Issues

1. File Upload Fails
   · Check file size (max 50MB)
   · Verify file format (.xlsx, .xls, .csv)
   · Ensure required columns exist
2. ERP Connection Errors
   · Verify API endpoint URLs
   · Check authentication credentials
   · Test network connectivity
3. Mapping Configuration Issues
   · Validate required field mappings
   · Check data transformation rules
   · Verify field name compatibility

Getting Help

· Check application logs for detailed error information
· Use the built-in validation tools in the dashboard
· Test with sample data first

---

📊 Monitoring & Analytics

The system provides comprehensive monitoring:

· Import Success Rates - Track successful vs failed imports
· Processing Times - Monitor performance metrics
· Error Analytics - Most common errors and solutions
· ERP Response Times - API performance monitoring

---

🔒 Security Features

· API Authentication - Secure API key management
· Data Validation - Input sanitization and validation
· Error Handling - Secure error messages without information leakage
· Access Logs - Complete audit trail

---

🤝 Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Code formatting
black app/ tests/
```

---

📄 License

This project is proprietary software. All rights reserved.

---

📞 Support

Technical Support

· Email: support@ygnb2b.com
· Response Time: 24-48 hours
· Support Hours: 9AM - 6PM (Yangon Time)

Developer

· Name: Ethan Victor
· Email: support@ygnb2b.com
· Specialization: Enterprise Integration Solutions

Issue Reporting

When reporting issues, please include:

1. Detailed description of the problem
2. Steps to reproduce
3. Error messages and logs
4. Sample Excel file (if related to import)

---

🚀 Deployment Status

https://render.com/images/deploy-to-render-button.svg

Live Demo: https://rangoon-middleware-demo.onrender.com

---

🎯 Use Cases

Retail Businesses

· Import customer data from multiple POS systems
· Sync product catalogs and pricing
· Automate sales data integration

Hospitality Industry

· Guest information synchronization
· Room charge and service billing
· Inventory management integration

Manufacturing

· Product master data synchronization
· Sales order processing
· Inventory level updates

---

Last Updated: September 2025
Version: 1.0.0
Developed by Ethan Victor • support@ygnb2b.com
