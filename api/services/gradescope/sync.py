"""
Gradescope Sync Module

High-level sync operations for Gradescope data.
"""
from typing import Dict, Any, Optional
import logging
from .client import GradescopeClient
from ..sheets.client import SheetsClient

logger = logging.getLogger(__name__)


class GradescopeSync:
    """
    Sync Gradescope grades to database and Google Sheets.
    
    Orchestrates:
    - Gradescope API access
    - Data transformation
    - Database persistence
    - Google Sheets export
    """
    
    def __init__(
        self,
        email: str,
        password: str,
        sheets_client: Optional[SheetsClient] = None
    ):
        """
        Initialize Gradescope sync.
        
        Args:
            email: Gradescope email
            password: Gradescope password
            sheets_client: Optional SheetsClient (created if not provided)
        """
        self.gs_client = GradescopeClient(timeout=1800)
        self.email = email
        self.password = password
        self.sheets_client = sheets_client or SheetsClient()
        
    def sync_course(
        self,
        course_id: str,
        spreadsheet_id: Optional[str] = None,
        save_to_db: bool = True,
        course_name: Optional[str] = None,
        course_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Sync a Gradescope course.
        
        Args:
            course_id: Gradescope course ID
            spreadsheet_id: Optional Google Sheets ID for export
            save_to_db: Whether to save to database (default True)
            course_name: Optional course name
            course_config: Optional course configuration with categories
            
        Returns:
            Dictionary with sync results
        """
        print(f"[DEBUG] Starting Gradescope sync for course {course_id}")
        logger.info(f"Starting Gradescope sync for course {course_id}")
        
        try:
            # Login to Gradescope
            print("[DEBUG] Attempting Gradescope login...")
            logger.info("Attempting Gradescope login...")
            login_result = self.gs_client.log_in(self.email, self.password)
            print(f"[DEBUG] Login result: {login_result}")
            logger.info(f"Login result: {login_result}")
            
            if not login_result:
                raise RuntimeError("Failed to login to Gradescope")
            
            # Get assignments for the course
            print("[DEBUG] Fetching course assignments...")
            logger.info("Fetching course assignments...")
            assignments_data = {}
            students_data = set()
            sheets_data = []  # 收集所有需要导出到 Sheets 的数据
            
            # Download all assignments and their scores
            print(f"[DEBUG] About to call _get_course_assignments({course_id})")
            course_assignments = self._get_course_assignments(course_id)
            print(f"[DEBUG] Retrieved {len(course_assignments)} assignments from Gradescope")
            logger.info(f"Retrieved {len(course_assignments)} assignments from Gradescope")
            
            for assignment_id, assignment_name in course_assignments.items():
                logger.info(f"Downloading scores for: {assignment_name} (ID: {assignment_id})")
                
                try:
                    # Download CSV scores for this assignment
                    scores_csv = self.gs_client.download_scores(course_id, assignment_id)
                    
                    if scores_csv:
                        # Ensure scores_csv is a string (not bytes)
                        if isinstance(scores_csv, bytes):
                            scores_csv = scores_csv.decode('utf-8')
                        
                        print(f"[DEBUG] Downloaded {len(scores_csv)} bytes for {assignment_name}")
                        
                        # Parse CSV and save to database if requested
                        if save_to_db:
                            self._save_assignment_to_db(
                                course_id=course_id,
                                assignment_id=assignment_id,
                                assignment_name=assignment_name,
                                scores_csv=scores_csv,
                                course_config=course_config
                            )
                        
                        # 收集 Sheets 数据（稍后批量导出）
                        if spreadsheet_id:
                            sheets_data.append({
                                'assignment_name': assignment_name,
                                'scores_csv': scores_csv
                            })
                        
                        assignments_data[assignment_id] = assignment_name
                        
                        # Count unique students
                        import csv
                        import io
                        reader = csv.DictReader(io.StringIO(scores_csv))
                        for row in reader:
                            if 'SID' in row:
                                students_data.add(row['SID'])
                
                except Exception as e:
                    logger.error(f"Failed to sync {assignment_name}: {e}")
                    continue
            
            # 批量导出到 Sheets（一次性处理所有作业）
            if spreadsheet_id and sheets_data:
                logger.info(f"Exporting summary to Sheets...")
                self._export_summary_to_sheets(spreadsheet_id, course_id)
            
            results = {
                "success": True,
                "course_id": course_id,
                "assignments_synced": len(assignments_data),
                "students_synced": len(students_data)
            }
            
            logger.info(f"Sync completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise
        finally:
            self.gs_client.logout()
    
    def close(self):
        """Close clients."""
        self.gs_client.logout()
        if self.sheets_client:
            self.sheets_client.close()
    
    def _get_course_assignments(self, course_id: str) -> Dict[str, str]:
        """
        Get all assignments for a course using Gradescope API.
        
        Args:
            course_id: Gradescope course ID
            
        Returns:
            Dict mapping assignment_id -> assignment_name
        """
        import re
        import json
        
        print(f"[DEBUG] Getting assignments for course {course_id}")
        
        try:
            # Get course assignments page
            url = f"{self.gs_client.base_url}/courses/{course_id}/assignments"
            response = self.gs_client.session.get(url)
            response.raise_for_status()
            
            # Get response content as string
            response_text = response.text
            
            # Find the gon (Global Object Notation) data which contains assignment info
            # Look for patterns like: "id":12345,"title":"Assignment Name"
            pattern = r'"id":(\d+),"title":"([^"]*)"'
            matches = re.findall(pattern, response_text)
            
            assignments = {}
            for assignment_id, assignment_name in matches:
                assignments[assignment_id] = assignment_name
            
            print(f"[DEBUG] Found {len(assignments)} assignments: {assignments}")
            logger.info(f"Found {len(assignments)} assignments")
            return assignments
            
        except Exception as e:
            print(f"[DEBUG] Error getting assignments: {e}")
            logger.error(f"Failed to get assignments: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _save_assignment_to_db(
        self,
        course_id: str,
        assignment_id: str,
        assignment_name: str,
        scores_csv: str,
        course_config: Optional[Any] = None
    ):
        """Save assignment scores to database from CSV string content."""
        try:
            import tempfile
            import os
            
            # Create temporary file to store CSV content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
                f.write(scores_csv)
                temp_filepath = f.name
            
            try:
                from api.core.ingest import write_assignment_scores_to_db
                
                # Extract course metadata from config
                course_categories = None
                course_name = None
                spreadsheet_id = None
                department = None
                course_number = None
                semester = None
                year = None
                instructor = None
                
                if course_config:
                    course_categories = course_config.get('assignment_categories', [])
                    course_name = course_config.get('name')
                    department = course_config.get('department')
                    course_number = course_config.get('course_number')
                    semester = course_config.get('semester')
                    year = course_config.get('year')
                    instructor = course_config.get('instructor')
                    spreadsheet_config = course_config.get('spreadsheet', {})
                    if isinstance(spreadsheet_config, dict):
                        spreadsheet_id = spreadsheet_config.get('id')
                
                write_assignment_scores_to_db(
                    course_gradescope_id=course_id,
                    assignment_id=assignment_id,
                    assignment_name=assignment_name,
                    csv_filepath=temp_filepath,
                    spreadsheet_id=spreadsheet_id,
                    course_name=course_name,
                    department=department,
                    course_number=course_number,
                    semester=semester,
                    year=year,
                    instructor=instructor,
                    course_categories=course_categories
                )
                print(f"[DEBUG] Saved {assignment_name} to database")
                logger.info(f"Saved {assignment_name} to database")
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_filepath):
                    os.remove(temp_filepath)
            
        except Exception as e:
            print(f"[DEBUG] Failed to save {assignment_name} to database: {e}")
            logger.error(f"Failed to save {assignment_name} to database: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_summary_to_sheets(
        self,
        spreadsheet_id: str,
        course_id: str
    ):
        """导出课程汇总表和类别统计到 Google Sheets（不导出单个作业）"""
        try:
            import pandas as pd
            import numpy as np
            from api.core.db import SessionLocal
            from api.core.models import Course, Assignment, Student, Submission
            
            session = SessionLocal()
            
            # 获取课程数据
            course = session.query(Course).filter(
                Course.gradescope_course_id == course_id
            ).first()
            
            if not course:
                logger.error(f"Course not found: {course_id}")
                session.close()
                return
            
            logger.info(f"Building summary sheets for {course.name}...")
            
            # 1. 构建学生 x 作业 的汇总表
            students = session.query(Student).all()
            assignments = session.query(Assignment).filter(
                Assignment.course_id == course.id
            ).all()
            
            # 构建汇总数据
            summary_data = []
            header = ['Student Email', 'Student Name'] + [a.title for a in assignments]
            summary_data.append(header)
            
            for student in students:
                row = [student.email or '', student.legal_name or '']
                for assignment in assignments:
                    sub = session.query(Submission).filter(
                        Submission.student_id == student.id,
                        Submission.assignment_id == assignment.id
                    ).first()
                    if sub and sub.total_score is not None:
                        row.append(float(sub.total_score))
                    else:
                        row.append('')
                summary_data.append(row)
            
            # 2. 构建按类别统计表
            from sqlalchemy import func
            category_stats = session.query(
                Assignment.category,
                func.count(Submission.id).label('submitted_count'),
                func.avg(Submission.total_score).label('avg_score'),
                func.max(Assignment.max_points).label('max_points')
            ).join(Submission, Submission.assignment_id == Assignment.id).filter(
                Assignment.course_id == course.id,
                Assignment.category.isnot(None)
            ).group_by(Assignment.category).all()
            
            category_data = [['Category', 'Assignments', 'Avg Score', 'Max Points']]
            for cat, count, avg_score, max_pts in category_stats:
                if cat and cat != 'Uncategorized':  # 忽略 Practice
                    category_data.append([
                        cat,
                        count,
                        round(float(avg_score), 2) if avg_score else '',
                        float(max_pts) if max_pts else ''
                    ])
            
            # 清理 NaN
            def clean_data(data):
                cleaned = []
                for row in data:
                    cleaned_row = []
                    for cell in row:
                        try:
                            if isinstance(cell, (float, np.floating)):
                                if not np.isfinite(cell):
                                    cleaned_row.append(None)
                                else:
                                    cleaned_row.append(cell)
                            else:
                                cleaned_row.append(cell)
                        except:
                            cleaned_row.append(cell)
                    cleaned.append(cleaned_row)
                return cleaned
            
            summary_data = clean_data(summary_data)
            category_data = clean_data(category_data)
            
            # 更新工作表
            spreadsheet = self.sheets_client.open_spreadsheet(spreadsheet_id)
            
            # Summary 表
            try:
                summary_ws = spreadsheet.worksheet('Summary')
                summary_ws.clear()
            except:
                summary_ws = spreadsheet.add_worksheet('Summary', rows=len(summary_data)+10, cols=26)
            
            summary_ws.update('A1', summary_data)
            logger.info(f"✅ Updated Summary sheet ({len(summary_data)} rows)")
            
            # Category Statistics 表
            try:
                cat_ws = spreadsheet.worksheet('Category Statistics')
                cat_ws.clear()
            except:
                cat_ws = spreadsheet.add_worksheet('Category Statistics', rows=10, cols=10)
            
            cat_ws.update('A1', category_data)
            logger.info(f"✅ Updated Category Statistics sheet")
            
            session.close()
            logger.info(f"✅ Successfully exported summary to Sheets")
            
        except Exception as e:
            logger.error(f"Summary export to Sheets failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _batch_export_to_sheets(
        self,
        spreadsheet_id: str,
        sheets_data: list
    ):
        """批量导出所有作业到 Google Sheets（已废弃 - 改用 _export_summary_to_sheets）"""
        try:
            import pandas as pd
            import io
            import time
            
            logger.info(f"Preparing batch export of {len(sheets_data)} assignments to Sheets")
            
            # 准备所有工作表数据
            requests = []
            sheet_id_map = {}
            
            # 获取现有工作表
            spreadsheet = self.sheets_client.open_spreadsheet(spreadsheet_id)
            existing_sheets = {ws.title: ws.id for ws in spreadsheet.worksheets()}
            
            # 为每个作业准备数据和请求
            for idx, item in enumerate(sheets_data):
                assignment_name = item['assignment_name']
                scores_csv = item['scores_csv']
                
                # 解析 CSV
                df = pd.read_csv(io.StringIO(scores_csv))
                
                # 清理数据（NaN/inf -> None）
                import numpy as np
                df_cleaned = df.replace([np.inf, -np.inf], None)
                df_cleaned = df_cleaned.where(pd.notna(df_cleaned), None)
                
                # 转换为列表并再次清理任何剩余的 nan 值
                data = [df_cleaned.columns.tolist()] + df_cleaned.values.tolist()
                
                # 最后一道清理：确保没有任何 nan/inf 残留
                def _final_clean(val):
                    try:
                        if isinstance(val, (float, np.floating)):
                            if not np.isfinite(val):
                                return None
                    except:
                        pass
                    return val
                
                data = [[_final_clean(cell) for cell in row] for row in data]
                
                # 获取或创建工作表
                if assignment_name in existing_sheets:
                    sheet_id = existing_sheets[assignment_name]
                    worksheet = spreadsheet.worksheet(assignment_name)
                else:
                    # 创建新工作表
                    worksheet = spreadsheet.add_worksheet(
                        title=assignment_name,
                        rows=len(data) + 10,
                        cols=len(data[0]) if data else 26
                    )
                    sheet_id = worksheet.id
                
                # 清空并更新工作表（使用 gspread 的 update 方法，它会自动批处理）
                worksheet.clear()
                worksheet.update('A1', data)
                
                logger.info(f"Exported {assignment_name} ({len(df)} rows)")
                
                # # 添加短暂延迟以避免过快
                # if (idx + 1) % 10 == 0:
                #     time.sleep(1)
            
            logger.info(f"✅ Successfully batch exported {len(sheets_data)} assignments to Sheets")
            
        except Exception as e:
            logger.error(f"Batch export to Sheets failed: {e}")
            import traceback
            traceback.print_exc()
    
    def _export_to_sheets(
        self,
        spreadsheet_id: str,
        assignment_name: str,
        scores_csv: str
    ):
        """Export assignment scores to Google Sheets (deprecated - use _batch_export_to_sheets)"""
        try:
            import pandas as pd
            import io
            import time
            import gspread
            from googleapiclient.errors import HttpError
            
            # Parse CSV to DataFrame
            df = pd.read_csv(io.StringIO(scores_csv))
            
            def _do_export():
                self.sheets_client.dataframe_to_sheet(
                    df=df,
                    spreadsheet_id=spreadsheet_id,
                    worksheet_title=assignment_name
                )

            try:
                _do_export()
            except (gspread.exceptions.APIError, HttpError) as e:
                status = getattr(getattr(e, 'response', None), 'status', None) or getattr(getattr(e, 'resp', None), 'status', None)
                if status == 429:
                    logger.warning("Hit Sheets write quota (429); sleeping 65s then retrying once")
                    time.sleep(65)
                    _do_export()
                else:
                    raise

            logger.info(f"Exported {assignment_name} to Google Sheets")
            
        except Exception as e:
            logger.error(f"Failed to export {assignment_name} to Sheets: {e}")
