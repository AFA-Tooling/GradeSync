#!/usr/bin/env python3
"""
快速同步成绩脚本

使用新的 api/services 架构同步课程成绩。
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

from api.sync.service import GradeSyncService


def sync_course(course_id: str):
    """
    同步指定课程的所有成绩（Gradescope + PrairieLearn + iClicker）
    
    Args:
        course_id: 课程 ID（在 config.json 中配置）
    """
    print("=" * 70)
    print(f"📊 开始同步课程: {course_id}")
    print("=" * 70)
    print()
    
    try:
        # 创建同步服务
        service = GradeSyncService(course_id=course_id)
        
        # 执行同步
        print("正在同步成绩...")
        result = service.sync_all()
        
        # 显示结果
        print("\n" + "=" * 70)
        print("✨ 同步完成！")
        print("=" * 70)
        print()
        print(f"课程: {result['course_name']}")
        print(f"时间: {result['timestamp']}")
        print(f"总体状态: {'✅ 成功' if result['overall_success'] else '❌ 失败'}")
        print()
        print("详细结果:")
        
        for r in result['results']:
            status = "✅" if r['success'] else "❌"
            print(f"  {status} {r['source'].upper()}: {r['message']}")
            if r.get('details'):
                for key, value in r['details'].items():
                    if isinstance(value, (int, str, bool)):
                        print(f"      - {key}: {value}")
        
        print()
        return result
        
    except ValueError as e:
        print(f"❌ 错误: {e}")
        print()
        print("请检查：")
        print("  1. config.json 中是否有该课程配置")
        print("  2. 环境变量是否正确配置")
        return None
    except Exception as e:
        print(f"❌ 同步失败: {e}")
        import traceback
        traceback.print_exc()
        return None


def list_courses():
    """列出所有可用课程"""
    from api.config_manager import get_config_manager
    
    print("=" * 70)
    print("📚 可用课程列表")
    print("=" * 70)
    print()
    
    config_mgr = get_config_manager()
    course_configs = config_mgr.list_course_configs()
    
    if not course_configs:
        print("⚠️  未找到任何课程配置")
        print("请在 config.json 中添加课程配置")
        return
    
    for config in course_configs:
        print(f"• {config.id}")
        print(f"  名称: {config.name}")
        print(f"  学期: {config.semester} {config.year}")
        
        # 显示启用的服务
        enabled = []
        if config.gradescope_enabled:
            enabled.append('Gradescope')
        if config.prairielearn_enabled:
            enabled.append('PrairieLearn')
        if config.iclicker_enabled:
            enabled.append('iClicker')
        
        print(f"  启用服务: {', '.join(enabled) if enabled else '无'}")
        print()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='GradeSync - 快速同步课程成绩',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 列出所有课程
  python sync_grades.py --list
  
  # 同步特定课程
  python sync_grades.py cs10_fa25
  
  # 同步多个课程
  python sync_grades.py cs10_fa25 cs61c_fa25

环境变量 (.env 文件):
  GRADESCOPE_EMAIL=your-email@example.com
  GRADESCOPE_PASSWORD=your-password
  PL_API_TOKEN=your-token
  ICLICKER_USERNAME=your-username
  ICLICKER_PASSWORD=your-password
  SERVICE_ACCOUNT_CREDENTIALS='{"type": "service_account", ...}'
  DATABASE_URL=postgresql://gradesync:changeme@localhost:5432/gradesync
        """
    )
    
    parser.add_argument(
        'course_ids',
        nargs='*',
        help='要同步的课程 ID（可以指定多个）'
    )
    
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='列出所有可用课程'
    )
    
    args = parser.parse_args()
    
    # 列出课程
    if args.list:
        list_courses()
        return
    
    # 如果没有指定课程，显示帮助
    if not args.course_ids:
        parser.print_help()
        print()
        list_courses()
        return
    
    # 同步指定的课程
    success_count = 0
    for course_id in args.course_ids:
        result = sync_course(course_id)
        if result and result.get('overall_success'):
            success_count += 1
        print()
    
    # 总结
    total = len(args.course_ids)
    print("=" * 70)
    print(f"完成：成功 {success_count}/{total} 个课程")
    print("=" * 70)


if __name__ == '__main__':
    main()
