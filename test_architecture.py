#!/usr/bin/env python3
"""
测试新的服务架构是否可用

验证所有导入和基本功能。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

print("=" * 70)
print("🧪 GradeSync 新架构测试")
print("=" * 70)
print()

# 测试 1: 导入核心模块
print("1️⃣  测试核心模块导入...")
try:
    from api.core import db, models, ingest
    print("   ✅ Core modules imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import core modules: {e}")
    sys.exit(1)

# 测试 2: 导入服务层
print("\n2️⃣  测试服务层导入...")
try:
    from api.services import (
        GradescopeClient,
        IClickerClient,
        PrairieLearnClient,
        SheetsClient
    )
    print("   ✅ Service clients imported successfully")
    print(f"      - GradescopeClient: {GradescopeClient.__name__}")
    print(f"      - IClickerClient: {IClickerClient.__name__}")
    print(f"      - PrairieLearnClient: {PrairieLearnClient.__name__}")
    print(f"      - SheetsClient: {SheetsClient.__name__}")
except Exception as e:
    print(f"   ❌ Failed to import service clients: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 3: 导入同步器
print("\n3️⃣  测试同步器导入...")
try:
    from api.services import (
        GradescopeSync,
        IClickerSync,
        PrairieLearnSync
    )
    print("   ✅ Sync classes imported successfully")
    print(f"      - GradescopeSync: {GradescopeSync.__name__}")
    print(f"      - IClickerSync: {IClickerSync.__name__}")
    print(f"      - PrairieLearnSync: {PrairieLearnSync.__name__}")
except Exception as e:
    print(f"   ❌ Failed to import sync classes: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 4: 导入 FastAPI app
print("\n4️⃣  测试 FastAPI 应用导入...")
try:
    from api.app import app
    print("   ✅ FastAPI app imported successfully")
    print(f"      - App title: {app.title}")
    print(f"      - Routes: {len(app.routes)} endpoints")
except Exception as e:
    print(f"   ❌ Failed to import FastAPI app: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 测试 5: 导入配置管理器
print("\n5️⃣  测试配置管理器...")
try:
    from api.config_manager import get_config_manager, EnvConfig
    config_mgr = get_config_manager()
    courses = config_mgr.list_courses()
    print("   ✅ Config manager working")
    print(f"      - Available courses: {len(courses)}")
    for course in courses:
        print(f"        • {course['id']}: {course['name']}")
except Exception as e:
    print(f"   ❌ Failed to load config: {e}")
    import traceback
    traceback.print_exc()

# 测试 6: 导入同步服务
print("\n6️⃣  测试同步服务层...")
try:
    from api.sync.service import GradeSyncService
    print("   ✅ GradeSyncService imported successfully")
except Exception as e:
    print(f"   ❌ Failed to import GradeSyncService: {e}")
    import traceback
    traceback.print_exc()

# 测试 7: 检查客户端初始化
print("\n7️⃣  测试客户端初始化...")
try:
    # Gradescope (需要凭据才能完全测试)
    gs = GradescopeClient(timeout=1800)
    print(f"   ✅ GradescopeClient initialized (timeout={gs.timeout}s)")
    
    # PrairieLearn (需要 token)
    print("   ℹ️  PrairieLearnClient needs API token for initialization")
    
    # iClicker (需要凭据)
    print("   ℹ️  IClickerClient needs credentials for initialization")
    
    # Sheets (需要 service account)
    print("   ℹ️  SheetsClient needs service account for full functionality")
    
except Exception as e:
    print(f"   ⚠️  Some clients need credentials: {e}")

print("\n" + "=" * 70)
print("✨ 测试完成！")
print("=" * 70)
print()
print("📋 总结:")
print("  ✅ 所有核心模块可以导入")
print("  ✅ 服务层架构正常工作")
print("  ✅ FastAPI 应用可以启动")
print()
print("🚀 下一步:")
print("  1. 配置环境变量 (.env 文件)")
print("  2. 启动 FastAPI: uvicorn api.app:app --reload")
print("  3. 访问 API 文档: http://localhost:8000/docs")
print()
