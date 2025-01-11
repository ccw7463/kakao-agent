import sqlite3
from loguru import logger
import os
from importlib.resources import files

class UserData:
    def __init__(self):
        self.db_path = os.path.join(files("data"),"user_data.db")
        self._initialize_db()
        
    def process_request(self,
                        user_id:str):
        """
            Des:
                사용자 정보를 찾거나 생성하는 함수
            Args:
                user_id: 사용자 ID
            Returns:
                user_info: 사용자 정보
        """
        user_info = self._get_or_create_user(user_id)
        return user_info

    def update_user_info(self, 
                         user_id:str, 
                         field:str, 
                         value:str):
        """
            Des:
                사용자 데이터 업데이트 함수
            Args:
                user_id: 사용자 ID
                field: 업데이트할 필드 이름 (personal_info 또는 personal_preference)
                value: 업데이트할 값
        """
        if field not in ["personal_info", "personal_preference"]:
            logger.error(f"잘못된 필드 이름: {field}")
            return
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f"UPDATE users SET {field} = ? WHERE id = ?", (value, user_id))
        conn.commit()
        conn.close()
        logger.info(f"{field} 정보 업데이트 완료. 사용자 id : {user_id}")
                
    def _initialize_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                personal_info TEXT,
                personal_preference TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def _get_or_create_user(self, 
                            user_id:str):
        """
            Des:
                사용자 정보를 찾거나 생성하는 함수
            Args:
                user_id: 사용자 ID
            Returns:
                user: 사용자 정보
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user_info = cursor.fetchone()
        if user_info:
            conn.close()
            logger.info(f"기존 사용자 데이터를 찾았습니다: {user_info}")
            return user_info
        else:
            cursor.execute("INSERT INTO users (id, personal_info, personal_preference) VALUES (?, ?, ?)",
                           (user_id,
                            "",
                            ""))
            conn.commit()
            conn.close()
            logger.info(f"새 사용자를 추가했습니다: {user_id}")
            return None