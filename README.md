# GradeSync

### About

GradeSync is a backend microservice that integrates with assessment platforms to fetch student grades and facilitate management of post-semester submissions. GradeSync enables students to submit coursework after the term ends and view their updated grades on the GradeView dashboard. GradeSync automates gradebook updates, eliminating the need for manual instructor intervention.


### Setting up Integrations
Navigate inside of each of the integrations' sub-folders in order to launch and deploy that particular integration. The current integrations supported with the google sheets as output include:
1. GradeScope - Containerized Cloud Deployment
2. PrairieLearn - Containerized Cloud Deployment
3. iClicker - Local Script


># GradeSync 统一API架构

## 概述

GradeSync已重构为统一的API驱动架构，通过中央API协调所有成绩同步操作。所有配置集中管理，支持多门课程。

## 架构设计

```
┌─────────────────────────────────────────────────────┐
│                   API Gateway                         │
│              (FastAPI - api/app.py)                  │
│                                                       │
│  Endpoints:                                          │
│  • POST /api/sync/{course_id}                       │
│  • POST /api/sync/{course_id}/gradescope            │
│  • POST /api/sync/{course_id}/prairielearn          │
│  • POST /api/sync/{course_id}/iclicker              │
│  • GET  /api/courses                                │
│  • GET  /api/summary/{course_id}                    │
└───────────────┬─────────────────────────────────────┘
                │
        ┌───────┴────────┐
        │                │
┌───────▼─────┐   ┌──────▼──────┐
│   Config    │   │   Grade     │
│   Manager   │   │    Sync     │
│             │   │   Service   │
└─────┬───────┘   └──────┬──────┘
      │                  │
      │          ┌───────┴────────┬──────────────┐
      │          │                │              │
┌─────▼────┐  ┌─▼──────────┐  ┌──▼────────┐  ┌─▼──────────┐
│ config   │  │ Gradescope │  │PrairieLearn│  │  iClicker  │
│  .json   │  │   Sync     │  │   Sync     │  │   Sync     │
└──────────┘  └────────────┘  └────────────┘  └────────────┘
                     │                │              │
                     └────────────────┴──────────────┘
                                    │
                          ┌─────────▼──────────┐
                          │   PostgreSQL DB    │
                          │  + Google Sheets   │
                          └────────────────────┘
```

## 配置文件结构

### 统一配置文件: `config.json`

```json
{
  "courses": [
    {
      "id": "cs10_fa25",
      "name": "CS10: The Beauty and Joy of Computing",
      "department": "COMPSCI",
      "course_number": "10",
      "semester": "Fall",
      "year": 2025,
      "instructor": "Dan Garcia",
      
      "gradescope": {
        "enabled": true,
        "course_id": "1098053",
        "sync_interval_hours": 24
      },
      
      "prairielearn": {
        "enabled": true,
        "course_id": "192475"
      },
      
      "iclicker": {
        "enabled": true,
        "course_names": [
          "[CS10 | Fa25] Discussion",
          "[CS10 | Fa25] Lab",
          "[CS10 | Fa25] Lecture"
        ]
      },
      
      "spreadsheet": {
        "id": "130Vsasjjy8cc8MWqpyVy32mS9lqhvy0mhJyOhfTAmOo",
        "scopes": ["https://www.googleapis.com/auth/spreadsheets"]
      },
      
      "database": {
        "enabled": true,
        "use_as_primary": true
      }
    }
  ],
  
  "global_settings": {
    "default_scopes": ["https://www.googleapis.com/auth/spreadsheets"],
    "csv_output_dir": "data/exports",
    "log_level": "INFO"
  }
}
```

### 环境变量: `.env`（根目录）

```bash
# Gradescope 凭证
GRADESCOPE_EMAIL=your_email@berkeley.edu
GRADESCOPE_PASSWORD=your_password

# PrairieLearn API Token
PL_API_TOKEN=your_pl_token

# iClicker 凭证
ICLICKER_USERNAME=your_username
ICLICKER_PASSWORD=your_password

# Google Service Account
SERVICE_ACCOUNT_CREDENTIALS={"type":"service_account",...}

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/gradesync
USE_DB_AS_PRIMARY=true
```

## API使用指南

### 1. 启动API服务器

```bash
cd api
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

### 2. 查看所有可用课程

```bash
curl http://localhost:8000/api/courses
```

**响应示例:**
```json
{
  "courses": [
    {
      "id": "cs10_fa25",
      "name": "CS10: The Beauty and Joy of Computing",
      "department": "COMPSCI",
      "course_number": "10",
      "semester": "Fall",
      "year": 2025,
      "instructor": "Dan Garcia",
      "enabled_sources": {
        "gradescope": true,
        "prairielearn": true,
        "iclicker": true
      }
    }
  ],
  "total": 1
}
```

### 3. 同步所有成绩（推荐）

**同步所有来源的成绩：**
```bash
curl -X POST http://localhost:8000/api/sync/cs10_fa25
```

这会自动：
- ✅ 同步Gradescope成绩
- ✅ 同步PrairieLearn成绩
- ✅ 同步iClicker成绩
- ✅ 更新数据库summary_sheets表
- ✅ 更新Google Sheets

**响应示例:**
```json
{
  "course_id": "cs10_fa25",
  "course_name": "CS10: The Beauty and Joy of Computing",
  "timestamp": "2026-01-14T15:30:00",
  "results": [
    {
      "source": "gradescope",
      "success": true,
      "message": "Successfully synced 25 assignments",
      "details": {
        "assignments_synced": 25,
        "students_updated": 150
      }
    },
    {
      "source": "prairielearn",
      "success": true,
      "message": "Successfully synced PrairieLearn grades",
      "details": {
        "assessments_synced": 10
      }
    },
    {
      "source": "iclicker",
      "success": true,
      "message": "Successfully synced iClicker for 3 sections",
      "details": {
        "sections": [...]
      }
    },
    {
      "source": "database",
      "success": true,
      "message": "Updated summary sheets: 150 students, 35 assignments"
    }
  ],
  "overall_success": true
}
```

### 4. 单独同步某个来源

**只同步Gradescope:**
```bash
curl -X POST http://localhost:8000/api/sync/cs10_fa25/gradescope
```

**只同步PrairieLearn:**
```bash
curl -X POST http://localhost:8000/api/sync/cs10_fa25/prairielearn
```

**只同步iClicker:**
```bash
curl -X POST http://localhost:8000/api/sync/cs10_fa25/iclicker
```

### 5. 获取Summary数据

```bash
curl http://localhost:8000/api/summary/cs10_fa25
```

**响应示例:**
```json
{
  "assignments": ["Lab 1", "Lab 2", "Project 1", ...],
  "students": [
    {
      "legal_name": "John Doe",
      "email": "john@berkeley.edu",
      "scores": {
        "Lab 1": 10,
        "Lab 2": 9.5,
        "Project 1": 95
      }
    }
  ],
  "categories": {
    "Lab 1": "Labs",
    "Project 1": "Projects"
  },
  "max_points": {
    "Lab 1": 10,
    "Project 1": 100
  }
}
```

## 添加新课程

### 步骤1: 更新config.json

在 `courses` 数组中添加新课程：

```json
{
  "id": "cs61a_sp26",
  "name": "CS61A: Structure and Interpretation of Computer Programs",
  "department": "COMPSCI",
  "course_number": "61A",
  "semester": "Spring",
  "year": 2026,
  "instructor": "John DeNero",
  
  "gradescope": {
    "enabled": true,
    "course_id": "123456"
  },
  
  "prairielearn": {
    "enabled": false
  },
  
  "iclicker": {
    "enabled": true,
    "course_names": ["[CS61A | Sp26] Lecture"]
  },
  
  "spreadsheet": {
    "id": "your_spreadsheet_id"
  },
  
  "database": {
    "enabled": true,
    "use_as_primary": true
  }
}
```

### 步骤2: 重启API服务器

```bash
# API会自动重新加载配置
# 或者手动重启
pkill -f "uvicorn app:app"
uvicorn app:app --reload
```

### 步骤3: 同步新课程

```bash
curl -X POST http://localhost:8000/api/sync/cs61a_sp26
```

## 代码模块说明

### 核心模块

| 文件 | 功能 | 说明 |
|------|------|------|
| `config.json` | 统一配置 | 所有课程和模块的配置 |
| `api/config_manager.py` | 配置管理器 | 加载和管理配置 |
| `api/grade_sync_service.py` | 成绩同步服务 | 协调各模块的同步 |
| `api/app.py` | API网关 | 统一的REST API接口 |

### 模块包装器

| 文件 | 功能 |
|------|------|
| `gradescope/gradescope_sync.py` | Gradescope同步包装 |
| `prairieLearn/pl_sync.py` | PrairieLearn同步包装 |
| `iclicker/iclicker_sync.py` | iClicker同步包装 |

### 数据库模块

| 文件 | 功能 |
|------|------|
| `api/models.py` | 数据库模型 |
| `api/ingest.py` | 数据导入 |
| `api/summary_from_db.py` | Summary查询 |

## 迁移指南

### 从旧架构迁移

**旧方式:**
```bash
# 需要分别运行多个脚本
cd gradescope && python gradescope_to_spreadsheet.py
cd ../prairieLearn && python pl_to_spreadsheet.py
cd ../iclicker && python iclicker_to_spreadsheet.py
cd ../scripts && python generate_summary_sheets.py
```

**新方式:**
```bash
# 一个API调用完成所有操作
curl -X POST http://localhost:8000/api/sync/cs10_fa25
```

### 配置迁移

1. **整合环境变量**: 将各个目录的`.env`文件内容合并到根目录`.env`
2. **整合配置文件**: 将各个模块的config JSON合并到 `config.json`
3. **更新引用**: 更新代码中对配置的引用，使用新的`config_manager`

## 优势

### ✅ 统一管理
- 所有配置集中在一个文件
- 一个API调用完成所有同步
- 统一的错误处理和日志

### ✅ 多课程支持
- 轻松添加新课程
- 每个课程独立配置
- 按课程独立同步

### ✅ 模块化设计
- 每个来源可独立启用/禁用
- 可单独同步某个来源
- 易于扩展新数据源

### ✅ 自动化友好
- RESTful API接口
- 易于集成到CI/CD
- 支持后台任务

## 自动化示例

### 定时同步（cron job）

```bash
# 编辑crontab
crontab -e

# 每天晚上11点同步所有课程
0 23 * * * curl -X POST http://localhost:8000/api/sync/cs10_fa25
0 23 * * * curl -X POST http://localhost:8000/api/sync/cs10_sp25
```

### Python脚本调用

```python
import requests

def sync_all_courses():
    courses = ["cs10_fa25", "cs10_sp25"]
    
    for course_id in courses:
        response = requests.post(
            f"http://localhost:8000/api/sync/{course_id}"
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ {course_id}: {result['overall_success']}")
        else:
            print(f"❌ {course_id}: Failed")

if __name__ == "__main__":
    sync_all_courses()
```

## 故障排查

### 检查配置是否正确

```bash
curl http://localhost:8000/api/courses | jq
```

### 查看API日志

```bash
# API服务器会输出详细日志
tail -f api_logs.txt
```

### 测试单个模块

```bash
# 只测试Gradescope
curl -X POST http://localhost:8000/api/sync/cs10_fa25/gradescope
```

### 验证数据库连接

```bash
psql $DATABASE_URL -c "SELECT COUNT(*) FROM courses;"
```

## 后续改进

- [ ] 添加身份验证和授权
- [ ] 支持Webhook自动触发同步
- [ ] 添加同步历史和审计日志
- [ ] 实现同步任务队列（Celery/RQ）
- [ ] 添加实时同步进度推送（WebSocket）
- [ ] 创建Web管理界面

## 总结

新架构实现了：
- ✅ **统一配置管理** - 一个config.json管理所有课程
- ✅ **统一API接口** - 通过REST API协调所有操作
- ✅ **多课程支持** - 轻松管理多门课程
- ✅ **模块化设计** - 每个数据源独立可控
- ✅ **自动化友好** - 易于集成和自动化

一个API调用即可完成所有成绩同步！🎉

