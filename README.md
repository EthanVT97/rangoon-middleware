Rangoon Middleware

🚀 အဆင့်မြင့် Excel Import System with Custom Mapping & ERP Integration

POS System များမှ ERP System များသို့ အချက်အလက်များ အလိုအလျောက် ချိတ်ဆက်ပေးနိုင်သော အဆင့်မြင့် Middleware Solution တစ်ခုဖြစ်ပါသည်။

---

✨ အဓိက စွမ်းဆောင်ရည်များ

🎛️ Custom Column Mapping စနစ်

· Drag & Drop Interface - အသုံးပြုရလွယ်ကူသော Web-based Mapping Configuration
· Flexible Field Mapping - Excel Column မှ ERP Field သို့ လွတ်လပ်စွာ Map လုပ်နိုင်ခြင်း
· Data Transformations - Uppercase, Trim, Phone Format အစရှိသော Data ပြောင်းလဲမှုများ
· Validation Rules - Required Fields နှင့် Data Validation Rules များ သတ်မှတ်နိုင်ခြင်း

📊 Excel Import စွမ်းရည်များ

· Multiple Formats - .xlsx, .xls, .csv ဖိုင်အမျိုးအစားများ ထောက်ပံ့ခြင်း
· Large File Handling - 50MB အထိ ဖိုင်ကြီးများကို Background Job Processing ဖြင့် လုပ်ဆောင်နိုင်ခြင်း
· Data Validation - Real-time Validation နှင့် Error Reporting
· Batch Processing - Record ထောင်ချီကို ထိရောက်စွာ လုပ်ဆောင်နိုင်ခြင်း

🔗 ERP Integration

· REST API Integration - ERP System များနှင့် ချောမွေ့စွာ ချိတ်ဆက်နိုင်ခြင်း
· Multiple Endpoints - Customers, Products, Sales, Inventory APIs များ ထောက်ပံ့ခြင်း
· Authentication Support - API Keys, OAuth, Token-based Authentication
· Error Handling - Automatic Retry with Exponential Backoff

📈 Dashboard & Monitoring

· Real-time Job Tracking - Import လုပ်ငန်းစဉ်များကို Real-time စောင့်ကြည့်နိုင်ခြင်း
· Error Reporting - Row-level Debugging ပါသော Error Logs များ
· Performance Metrics - Processing Times နှင့် Success Rates များ ခြေရာခံခြင်း
· Upload History - Import မှတ်တမ်းများ အားလုံး သိမ်းဆည်းထားခြင်း

---

🛠️ Technology Stack

Backend

· FastAPI - Modern, fast web framework for APIs
· Python 3.11+ - High-performance programming language
· Supabase - Real-time Database with Authentication
· SQLAlchemy - SQL toolkit and ORM
· Pandas - Data analysis and manipulation library

Frontend

· HTML5/CSS3 - Responsive web interface
· JavaScript - Interactive dashboard functionality
· Jinja2 - Templating engine
· WebSocket - Real-time live updates

Deployment

· Render - Cloud platform for deployment
· Supabase - Production-ready PostgreSQL database
· Docker - Containerization support

---

🚀 စတင်အသုံးပြုနည်း

Prerequisites

· Python 3.11+
· Git
· Render account (for deployment)
· Supabase account (for database)

Local Development

1. Repository Clone လုပ်ခြင်း
   ```bash
   git clone https://github.com/Ethanvt97/rangoon-middleware.git
   cd rangoon-middleware
   ```
2. Dependencies Installation
   ```bash
   pip install -r requirements.txt
   ```
3. Environment Variables Setup
   ```env
   SUPABASE_URL=your_supabase_project_url
   SUPABASE_KEY=your_supabase_anon_key
   SECRET_KEY=your-jwt-secret-key
   ERP_BASE_URL=https://your-erp-api.com
   ERP_API_KEY=your-erp-api-key
   ```
4. Application Run
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
5. Access Application
   · Dashboard: http://localhost:8000
   · API Documentation: http://localhost:8000/docs

Production Deployment

1. Render ပေါ်တွင် Deploy လုပ်ခြင်း
   · GitHub repository ကို Render သို့ ချိတ်ဆက်ပါ
   · render.yaml configuration ကို အသုံးပြုပါ
   · Git push တိုင်း auto-deploy ဖြစ်မည်
2. Supabase Database Setup
   ```sql
   -- Supabase SQL Editor တွင် အောက်ပါ SQL ကို Run ပါ
   -- (Complete SQL schema provided in documentation)
   ```

---

📖 အသုံးပြုနည်း လမ်းညွှန်

Step 1: User Registration & Login

1. Dashboard သို့ ဝင်ရောက်ပါ
2. Register/Login လုပ်ပါ
3. User Profile ကို ပြင်ဆင်ပါ

Step 2: ERP Connection Configuration

1. Dashboard → ERP Configuration သို့ သွားပါ
2. ERP API details များ ထည့်သွင်းပါ:
   · Base URL
   · API Key
   · Endpoint mappings

Step 3: Column Mapping Creation

1. "Create New Mapping" ကို နှိပ်ပါ
2. Source Excel columns များ သတ်မှတ်ပါ:
   · Column names and data types
   · Required field settings
3. Target ERP fields များသို့ Map လုပ်ပါ:
   · Field mappings
   · Data transformations
   · Default values

Step 4: Excel File Import

1. Mapping configuration ကို ရွေးချယ်ပါ
2. Excel/CSV file ကို upload လုပ်ပါ
3. Real-time processing ကို စောင့်ကြည့်ပါ
4. Results နှင့် errors များကို သုံးသပ်ပါ

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

Authentication Endpoints

· POST /auth/register - User registration
· POST /auth/login - User login
· GET /auth/me - Get current user info

ERP Integration

· POST /api/erp/connection - Configure ERP connection
· GET /api/erp/test - Test ERP connection
· POST /api/erp/sync - Manual sync trigger

Real-time Monitoring

· WS /monitoring/ws/{user_id} - WebSocket for real-time updates
· GET /monitoring/metrics - Real-time performance metrics
· GET /monitoring/errors - Recent error reports

---

🗂️ Project Structure

```
pos-erp-middleware/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── models.py              # Data models & Pydantic schemas
│   ├── database.py            # Database configuration
│   ├── auth.py               # Authentication & authorization
│   ├── erp_integration.py     # ERP API communication
│   ├── websocket_manager.py   # Real-time WebSocket management
│   ├── monitoring.py          # Live monitoring system
│   └── utils/
│       ├── file_processor.py  # Excel/CSV processing
│       ├── validators.py      # Data validation
│       └── mapping_engine.py  # Column mapping logic
├── routes/
│   ├── auth_routes.py         # Authentication routes
│   ├── dashboard_routes.py    # Dashboard routes
│   ├── mapping_routes.py      # Column mapping routes
│   ├── import_routes.py       # File import routes
│   └── monitoring_routes.py   # Monitoring routes
├── templates/                 # HTML templates
│   ├── dashboard.html         # Main dashboard
│   ├── mapping_config.html    # Mapping configuration
│   └── upload_status.html     # Upload status page
├── static/                   # CSS, JavaScript, assets
│   ├── css/
│   │   └── style.css          # Custom styles
│   └── js/
│       ├── dashboard.js       # Dashboard functionality
│       └── mapping-config.js  # Mapping configuration
├── tests/                    # Test suites
├── requirements.txt          # Python dependencies
├── runtime.txt              # Python version
├── render.yaml              # Render deployment config
├── .env                     # Environment variables
└── README.md               # This file
```

---

🔧 Configuration Examples

Column Mapping Configuration

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
  },
  "mapping_rules": {
    "erp_endpoint": "customers"
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

Common Issues & Solutions

1. File Upload ပြဿနာများ
   · ဖိုင်အရွယ်အစား စစ်ဆေးပါ (max 50MB)
   · ဖိုင်အမျိုးအစား မှန်ရဲ့လား (.xlsx, .xls, .csv)
   · Required columns ရှိရဲ့လား စစ်ဆေးပါ
2. ERP Connection Errors
   · API endpoint URLs များ မှန်ရဲ့လား
   · Authentication credentials များ စစ်ဆေးပါ
   · Network connectivity စစ်ဆေးပါ
3. Mapping Configuration Issues
   · Required field mappings များ စစ်ဆေးပါ
   · Data transformation rules များ ပြန်စစ်ပါ
   · Field name compatibility စစ်ဆေးပါ

Getting Help

· Application logs များကို စစ်ဆေးပါ
· Dashboard အတွင်းရှိ built-in validation tools များ အသုံးပြုပါ
· Sample data ဖြင့် အရင် test လုပ်ပါ

---

📊 Monitoring & Analytics

စနစ်တွင် အောက်ပါ Monitoring Features များ ပါဝင်ပါသည်:

· Import Success Rates - အောင်မြင်သော vs မအောင်မြင်သော Imports များ ခြေရာခံခြင်း
· Processing Times - Performance metrics များ စောင့်ကြည့်ခြင်း
· Error Analytics - အဖြစ်များသော Errors များနှင့် Solutions များ
· ERP Response Times - API Performance Monitoring
· Real-time Live Updates - WebSocket-based live monitoring

---

🔒 Security Features

· User Authentication - Supabase Auth with JWT tokens
· API Authentication - Secure API key management
· Data Validation - Input sanitization and validation
· Error Handling - Secure error messages without information leakage
· Access Logs - Complete audit trail
· Row Level Security - Database-level security policies

---

🤝 Contributing

Contributions များကို ကြိုဆိုပါသည်! ကျေးဇူးပြု၍:

1. Repository ကို Fork လုပ်ပါ
2. Feature branch တစ်ခု Create လုပ်ပါ
3. သင့်ရဲ့ Changes များကို ပြုလုပ်ပါ
4. Tests များ ထည့်သွင်းပါ
5. Pull request Submit လုပ်ပါ

Development Setup

```bash
# Development dependencies installation
pip install -r requirements.txt

# Tests run
pytest tests/

# Code formatting
black app/ tests/
```

---

📄 License

ဤ Project သည် proprietary software ဖြစ်ပါသည်။ သက်ဆိုင်ရာ အခွင့်အရေးအားလုံး ရယူထားပါသည်။

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

ပြဿနာများ Report လုပ်သည့်အခါ အောက်ပါအချက်များ ထည့်သွင်းပေးပါ:

1. ပြဿနာအကြောင်း အသေးစိတ်ဖော်ပြချက်
2. ပြန်လည်ဖြစ်ပွားနိုင်သော Steps များ
3. Error messages နှင့် logs များ
4. Sample Excel file (import နှင့်ဆိုင်လျှင်)

---

🚀 Deployment Status

https://render.com/images/deploy-to-render-button.svg

Live Demo: https://rangoon-middleware-demo.onrender.com

---

🎯 Use Cases

Retail Businesses

· POS Systems များမှ Customer Data များ Import လုပ်ခြင်း
· Product Catalogs နှင့် Pricing များ Sync လုပ်ခြင်း
· Sales Data Integration များ အလိုအလျောက်လုပ်ဆောင်ခြင်း

Hospitality Industry

· Guest Information Synchronization
· Room Charge နှင့် Service Billing များ
· Inventory Management Integration

Manufacturing

· Product Master Data Synchronization
· Sales Order Processing
· Inventory Level Updates

---

Last Updated: September 2025
Version: 1.0.0
Developed by Ethan Victor • support@ygnb2b.com
