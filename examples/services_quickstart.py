#!/usr/bin/env python3
"""
GradeSync Services Quick Start Guide

演示如何使用新的服务层架构。
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv()

def example_gradescope():
    """示例：同步 Gradescope 课程"""
    from api.services import GradescopeSync
    
    print("=" * 60)
    print("Gradescope 同步示例")
    print("=" * 60)
    
    sync = GradescopeSync(
        email=os.getenv("GRADESCOPE_EMAIL"),
        password=os.getenv("GRADESCOPE_PASSWORD")
    )
    
    result = sync.sync_course(
        course_id="12345",
        spreadsheet_id="your-spreadsheet-id",
        save_to_db=True
    )
    
    print(f"✓ 同步了 {result['assignments_synced']} 个作业")
    print(f"✓ 同步了 {result['students_synced']} 个学生")
    print()


def example_iclicker():
    """示例：同步 iClicker 课程"""
    from api.services import IClickerSync
    
    print("=" * 60)
    print("iClicker 同步示例")
    print("=" * 60)
    
    sync = IClickerSync(
        username=os.getenv("ICLICKER_USERNAME"),
        password=os.getenv("ICLICKER_PASSWORD")
    )
    
    result = sync.sync_courses(
        course_names=[
            "[CS10 | Fa25] Lecture",
            "[CS10 | Fa25] Lab"
        ],
        spreadsheet_id="your-spreadsheet-id"
    )
    
    print(f"✓ 同步了 {result['courses_synced']} 门课程")
    for course in result['courses']:
        print(f"  - {course['course']}: {course['records']} 条记录")
    print()


def example_prairielearn():
    """示例：同步 PrairieLearn 课程"""
    from api.services import PrairieLearnSync
    
    print("=" * 60)
    print("PrairieLearn 同步示例")
    print("=" * 60)
    
    sync = PrairieLearnSync(
        api_token=os.getenv("PL_API_TOKEN")
    )
    
    result = sync.sync_course(
        course_id="67890",
        spreadsheet_id="your-spreadsheet-id",
        save_to_db=True
    )
    
    print(f"✓ 课程: {result['course_title']}")
    print(f"✓ 同步了 {result['assessments_synced']} 个评估")
    print(f"✓ 同步了 {result['students_synced']} 个学生")
    print()


def example_sheets_basic():
    """示例：基础 Google Sheets 操作"""
    from api.services import SheetsClient
    import pandas as pd
    
    print("=" * 60)
    print("Google Sheets 基础操作示例")
    print("=" * 60)
    
    client = SheetsClient()
    
    # 创建示例数据
    df = pd.DataFrame({
        'Name': ['Alice', 'Bob', 'Charlie'],
        'Score': [95, 87, 92],
        'Grade': ['A', 'B', 'A']
    })
    
    # 写入 Sheets
    spreadsheet_id = "your-spreadsheet-id"
    client.dataframe_to_sheet(
        df=df,
        spreadsheet_id=spreadsheet_id,
        worksheet_title="Sample Grades"
    )
    print("✓ 写入了 3 行数据到 'Sample Grades'")
    
    # 读取 Sheets
    result_df = client.sheet_to_dataframe(
        spreadsheet_id=spreadsheet_id,
        worksheet_title="Sample Grades"
    )
    print(f"✓ 读取了 {len(result_df)} 行数据")
    print()


def example_clients_only():
    """示例：只使用客户端（不使用同步器）"""
    from api.services import (
        GradescopeClient,
        IClickerClient,
        PrairieLearnClient,
        SheetsClient
    )
    
    print("=" * 60)
    print("客户端直接使用示例")
    print("=" * 60)
    
    # Gradescope 客户端
    gs = GradescopeClient(timeout=1800)
    print("✓ Gradescope 客户端已创建")
    
    # iClicker 客户端（使用 context manager）
    with IClickerClient(
        username=os.getenv("ICLICKER_USERNAME", ""),
        password=os.getenv("ICLICKER_PASSWORD", ""),
        headless=True
    ) as ic:
        print("✓ iClicker 客户端已创建（headless 模式）")
    
    # PrairieLearn 客户端
    with PrairieLearnClient(
        api_token=os.getenv("PL_API_TOKEN", "")
    ) as pl:
        print("✓ PrairieLearn 客户端已创建")
    
    # Sheets 客户端
    sheets = SheetsClient()
    print("✓ Google Sheets 客户端已创建")
    print()


def example_import_patterns():
    """示例：不同的导入方式"""
    print("=" * 60)
    print("导入模式示例")
    print("=" * 60)
    
    # 方式 1: 从统一入口导入（推荐）
    from api.services import (
        GradescopeClient,
        IClickerClient,
        PrairieLearnClient,
        SheetsClient
    )
    print("✓ 方式 1: 从 api.services 统一导入")
    
    # 方式 2: 从各个模块导入
    from api.services.gradescope import GradescopeClient, GradescopeSync
    from api.services.iclicker import IClickerClient, IClickerSync
    from api.services.prairielearn import PrairieLearnClient, PrairieLearnSync
    from api.services.sheets import SheetsClient
    print("✓ 方式 2: 从各个子模块导入")
    
    # 方式 3: 导入数据模型
    from api.services.prairielearn import CourseInfo, AssessmentInfo
    print("✓ 方式 3: 导入数据模型（Type hints）")
    print()


def show_architecture():
    """显示架构说明"""
    print("=" * 60)
    print("GradeSync 服务层架构")
    print("=" * 60)
    print("""
分层设计:

1. Client (客户端)
   - 封装底层 API/自动化
   - 无业务逻辑
   - 可独立使用
   - 例：GradescopeClient, PrairieLearnClient

2. Sync (同步器)
   - 协调数据同步
   - 包含业务逻辑
   - 调用多个客户端
   - 例：GradescopeSync, IClickerSync

3. Shared Services (共享服务)
   - 跨服务复用
   - 统一接口
   - 例：SheetsClient (被所有同步器使用)

使用建议:
  - 简单任务: 直接使用 Client
  - 完整同步: 使用 Sync
  - 批量操作: 使用 SheetsClient
    """)


def main():
    """主函数"""
    print("\n")
    print("🚀 GradeSync Services 快速入门")
    print("=" * 60)
    print()
    
    # 显示架构
    show_architecture()
    
    # 导入示例
    example_import_patterns()
    
    # 客户端示例
    example_clients_only()
    
    print("💡 提示:")
    print("  - 所有客户端支持 context manager (with 语句)")
    print("  - 同步器会自动处理登录/登出")
    print("  - SheetsClient 内置重试和错误处理")
    print("  - Type hints 让 IDE 提供更好的代码补全")
    print()
    
    print("📚 更多信息:")
    print("  - 服务文档: api/services/README.md")
    print("  - 重构总结: docs/REFACTORING_SUMMARY.md")
    print("  - 项目结构: PROJECT_STRUCTURE.md")
    print()
    
    # 注意：实际的同步示例需要真实的凭据
    print("⚠️  注意: 实际同步示例需要配置环境变量:")
    print("  - GRADESCOPE_EMAIL / GRADESCOPE_PASSWORD")
    print("  - ICLICKER_USERNAME / ICLICKER_PASSWORD")
    print("  - PL_API_TOKEN")
    print("  - GOOGLE_APPLICATION_CREDENTIALS (可选)")
    print()


if __name__ == "__main__":
    main()
