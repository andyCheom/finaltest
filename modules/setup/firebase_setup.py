"""Firebase 프로젝트 설정 모듈"""

import logging
import os
import json
import subprocess
from typing import Dict, Optional, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build

from ..config import Config
from ..auth import get_credentials



logger = logging.getLogger(__name__)

class FirebaseSetupManager:
    """Firebase 프로젝트 설정 관리자"""
    
    def __init__(self):
        self.credentials = None
        self.project_id = None
        self.firebase_management = None
        
    
    def initialize(self) -> bool:
        """Firebase 클라이언트 초기화"""
        try:
            # 먼저 인증 초기화
            from ..auth import initialize_auth
            if not initialize_auth():
                logger.error("❌ GCP 인증 초기화에 실패했습니다")
                return False
                
            self.credentials = get_credentials()
            if not self.credentials:
                logger.error("❌ GCP 인증 정보를 가져올 수 없습니다")
                return False
                
            self.project_id = Config.PROJECT_ID
            if not self.project_id:
                logger.error("❌ PROJECT_ID 환경변수가 설정되지 않았습니다")
                return False
                
            # Firebase Management API 클라이언트
            self.firebase_management = build('firebase', 'v1beta1', credentials=self.credentials)
            
            logger.info(f"✅ Firebase 클라이언트 초기화 완료 - Project: {self.project_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase 클라이언트 초기화 실패: {e}")
            return False
    
    def check_firebase_cli(self) -> bool:
        """Firebase CLI 설치 및 로그인 상태 확인"""
        try:
            # Firebase CLI 설치 확인
            result = subprocess.run(['firebase', '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                logger.error("❌ Firebase CLI가 설치되지 않았습니다")
                logger.info("💡 설치 방법: npm install -g firebase-tools")
                return False
            
            logger.info(f"✅ Firebase CLI 설치됨: {result.stdout.strip()}")
            
            # 로그인 상태 확인
            result = subprocess.run(['firebase', 'projects:list'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.warning("⚠️ Firebase CLI 로그인이 필요합니다")
                logger.info("💡 로그인 방법: firebase login")
                return False
            
            logger.info("✅ Firebase CLI 로그인 상태 확인됨")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error("❌ Firebase CLI 명령 시간 초과")
            return False
        except FileNotFoundError:
            logger.error("❌ Firebase CLI를 찾을 수 없습니다")
            logger.info("💡 설치 방법: npm install -g firebase-tools")
            return False
        except Exception as e:
            logger.error(f"❌ Firebase CLI 확인 실패: {e}")
            return False
    
    def enable_firebase_project(self) -> bool:
        """GCP 프로젝트에서 Firebase 활성화"""
        try:
            # Firebase 프로젝트 존재 확인
            try:
                project = self.firebase_management.projects().get(
                    name=f"projects/{self.project_id}"
                ).execute()
                
                if project.get('state') == 'ACTIVE':
                    logger.info(f"✅ Firebase 프로젝트 '{self.project_id}' 이미 활성화됨")
                    return True
                    
            except Exception:
                pass  # 프로젝트가 없으면 생성
            
            # Firebase 프로젝트 생성/활성화
            logger.info(f"🔄 Firebase 프로젝트 '{self.project_id}' 활성화 중...")
            
            # Firebase 프로젝트 추가
            operation = self.firebase_management.projects().addFirebase(
                project=f"projects/{self.project_id}"
            ).execute()
            
            logger.info(f"🔄 Firebase 활성화 중... (Operation: {operation.get('name')})")
            
            # 활성화 완료 대기
            import time
            for i in range(30):  # 최대 5분 대기
                time.sleep(10)
                try:
                    project = self.firebase_management.projects().get(
                        name=f"projects/{self.project_id}"
                    ).execute()
                    
                    if project.get('state') == 'ACTIVE':
                        logger.info(f"✅ Firebase 프로젝트 활성화 완료")
                        return True
                        
                except Exception:
                    pass
                
                if i % 6 == 0:  # 1분마다 로그
                    logger.info(f"🔄 Firebase 활성화 대기 중... ({i//6 + 1}/5분)")
            
            logger.warning("⚠️ Firebase 활성화 시간 초과")
            return False
            
        except Exception as e:
            logger.error(f"❌ Firebase 프로젝트 활성화 실패: {e}")
            return False
    
    def setup_firebase_hosting(self) -> bool:
        """Firebase Hosting 설정"""
        try:
            # firebase.json 파일 확인
            if not os.path.exists('firebase.json'):
                logger.info("🔄 firebase.json 파일 생성 중...")
                
                firebase_config = {
                    "hosting": {
                        "public": "public",
                        "ignore": [
                            "firebase.json",
                            "**/.*",
                            "**/node_modules/**"
                        ],
                        "rewrites": [
                            {
                                "source": "/api/**",
                                "run": {
                                    "serviceId": f"{self.project_id}-graphrag-api",
                                    "region": "asia-northeast3"
                                }
                            },
                            {
                                "source": "**",
                                "destination": "/index.html"
                            }
                        ]
                    }
                }
                
                with open('firebase.json', 'w', encoding='utf-8') as f:
                    json.dump(firebase_config, f, indent=2, ensure_ascii=False)
                
                logger.info("✅ firebase.json 파일 생성 완료")
            else:
                logger.info("✅ firebase.json 파일 이미 존재함")
            
            # .firebaserc 파일 확인
            if not os.path.exists('.firebaserc'):
                logger.info("🔄 .firebaserc 파일 생성 중...")
                
                firebaserc_config = {
                    "projects": {
                        "default": self.project_id
                    }
                }
                
                with open('.firebaserc', 'w', encoding='utf-8') as f:
                    json.dump(firebaserc_config, f, indent=2)
                
                logger.info("✅ .firebaserc 파일 생성 완료")
            else:
                logger.info("✅ .firebaserc 파일 이미 존재함")
            
            # Firebase CLI로 프로젝트 연결 확인
            if self.check_firebase_cli():
                try:
                    result = subprocess.run(
                        ['firebase', 'use', self.project_id], 
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        logger.info(f"✅ Firebase 프로젝트 '{self.project_id}' 연결 완료")
                    else:
                        logger.warning(f"⚠️ Firebase 프로젝트 연결 실패: {result.stderr}")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Firebase CLI 프로젝트 연결 실패: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Firebase Hosting 설정 실패: {e}")
            return False
    
    def create_firebase_app(self, app_id: str = None, display_name: str = None) -> Optional[str]:
        """Firebase 웹 앱 생성"""
        try:
            if not app_id:
                app_id = f"{self.project_id}-web-app"
            
            if not display_name:
                display_name = f"{self.project_id.replace('-', ' ').title()} Web App"
            
            # 기존 앱 확인
            try:
                apps = self.firebase_management.projects().webApps().list(
                    parent=f"projects/{self.project_id}"
                ).execute()
                
                for app in apps.get('apps', []):
                    if app.get('appId') == app_id or app.get('displayName') == display_name:
                        logger.info(f"✅ Firebase 웹 앱 '{display_name}' 이미 존재함")
                        return app.get('appId')
                        
            except Exception:
                pass
            
            # 웹 앱 생성
            logger.info(f"🔄 Firebase 웹 앱 '{display_name}' 생성 중...")
            
            web_app = {
                'displayName': display_name
            }
            
            operation = self.firebase_management.projects().webApps().create(
                parent=f"projects/{self.project_id}",
                body=web_app
            ).execute()
            
            logger.info(f"🔄 웹 앱 생성 중... (Operation: {operation.get('name')})")
            
            # 생성 완료 대기
            import time
            for i in range(30):  # 최대 5분 대기
                time.sleep(10)
                try:
                    apps = self.firebase_management.projects().webApps().list(
                        parent=f"projects/{self.project_id}"
                    ).execute()
                    
                    for app in apps.get('apps', []):
                        if app.get('displayName') == display_name:
                            app_id = app.get('appId')
                            logger.info(f"✅ Firebase 웹 앱 생성 완료 - App ID: {app_id}")
                            return app_id
                            
                except Exception:
                    pass
                
                if i % 6 == 0:  # 1분마다 로그
                    logger.info(f"🔄 웹 앱 생성 대기 중... ({i//6 + 1}/5분)")
            
            logger.warning("⚠️ 웹 앱 생성 시간 초과")
            return None
            
        except Exception as e:
            logger.error(f"❌ Firebase 웹 앱 생성 실패: {e}")
            return None
    
    def get_firebase_config(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Firebase 앱 설정 정보 가져오기"""
        try:
            config = self.firebase_management.projects().webApps().getConfig(
                name=f"projects/{self.project_id}/webApps/{app_id}"
            ).execute()
            
            logger.info("✅ Firebase 설정 정보 가져오기 완료")
            return config
            
        except Exception as e:
            logger.error(f"❌ Firebase 설정 정보 가져오기 실패: {e}")
            return None
    
    def validate_firebase_setup(self) -> Dict[str, bool]:
        """Firebase 설정 검증"""
        results = {}
        
        try:
            # Firebase 프로젝트 상태 확인
            try:
                project = self.firebase_management.projects().get(
                    name=f"projects/{self.project_id}"
                ).execute()
                results['firebase_project'] = project.get('state') == 'ACTIVE'
            except Exception:
                results['firebase_project'] = False
            
            # firebase.json 파일 확인
            results['firebase_config'] = os.path.exists('firebase.json')
            
            # .firebaserc 파일 확인
            results['firebaserc'] = os.path.exists('.firebaserc')
            
            # Firebase CLI 확인
            results['firebase_cli'] = self.check_firebase_cli()
            
            logger.info(f"✅ Firebase 설정 검증 완료: {results}")
            return results
            
        except Exception as e:
            logger.error(f"❌ Firebase 설정 검증 실패: {e}")
            return {}
    
    def create_firebase_service_account(self, 
                                      service_account_id: str = None,
                                      display_name: str = None,
                                      description: str = None) -> Optional[str]:
        """Firebase 배포용 서비스 계정 생성 및 키 파일 다운로드"""
        try:
            if not service_account_id:
                # 서비스 계정 ID는 6-30자 제한
                project_short = self.project_id.replace('-', '')[:15]  # 프로젝트 ID 단축
                service_account_id = f"{project_short}-firebase"
            
            if not display_name:
                display_name = f"Firebase Deploy Service Account"
            
            if not description:
                description = f"Firebase 호스팅 배포용 서비스 계정"
            
            # IAM 클라이언트
            iam_service = build('iam', 'v1', credentials=self.credentials)
            
            service_account_email = f"{service_account_id}@{self.project_id}.iam.gserviceaccount.com"
            
            # 서비스 계정 존재 확인
            try:
                existing_sa = iam_service.projects().serviceAccounts().get(
                    name=f"projects/{self.project_id}/serviceAccounts/{service_account_email}"
                ).execute()
                logger.info(f"✅ Firebase 서비스 계정 '{service_account_id}' 이미 존재함")
            except Exception:
                # 서비스 계정 생성
                logger.info(f"🔄 Firebase 서비스 계정 '{service_account_id}' 생성 중...")
                
                service_account = {
                    'accountId': service_account_id,
                    'serviceAccount': {
                        'displayName': display_name,
                        'description': description
                    }
                }
                
                iam_service.projects().serviceAccounts().create(
                    name=f"projects/{self.project_id}",
                    body=service_account
                ).execute()
                
                logger.info(f"✅ Firebase 서비스 계정 '{service_account_id}' 생성 완료")
                
                # 서비스 계정 생성 완료 대기 (권한 부여 전)
                import time
                logger.info("🔄 서비스 계정 생성 완료 대기 중... (30초)")
                time.sleep(30)
            
            # Firebase 배포에 필요한 역할 부여
            required_roles = [
                # Firebase 관리 권한
                'roles/firebase.admin',
                'roles/firebasehosting.admin',
                
                # Cloud Storage 권한 (Firebase 호스팅 파일 저장용)
                'roles/storage.admin',
                
                # Cloud Build 권한 (배포 파이프라인용)
                'roles/cloudbuild.builds.builder',
                'roles/source.reader',
                
                # 로깅 권한
                'roles/logging.logWriter',
                
                # IAM 권한
                'roles/iam.serviceAccountUser',
                'roles/iam.serviceAccountTokenCreator'
            ]
            
            resource_manager = build('cloudresourcemanager', 'v1', credentials=self.credentials)
            
            for role in required_roles:
                try:
                    # 현재 IAM 정책 가져오기
                    policy = resource_manager.projects().getIamPolicy(
                        resource=self.project_id
                    ).execute()
                    
                    # 바인딩 추가
                    binding_exists = False
                    for binding in policy.get('bindings', []):
                        if binding['role'] == role:
                            if f"serviceAccount:{service_account_email}" not in binding['members']:
                                binding['members'].append(f"serviceAccount:{service_account_email}")
                            binding_exists = True
                            break
                    
                    if not binding_exists:
                        policy.setdefault('bindings', []).append({
                            'role': role,
                            'members': [f"serviceAccount:{service_account_email}"]
                        })
                    
                    # 정책 업데이트
                    resource_manager.projects().setIamPolicy(
                        resource=self.project_id,
                        body={'policy': policy}
                    ).execute()
                    
                    logger.info(f"✅ Firebase 역할 '{role}' 부여 완료")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Firebase 역할 '{role}' 부여 실패: {e}")
            
            # 키 파일 생성
            logger.info("🔄 Firebase 서비스 계정 키 파일 생성 중...")
            
            key = iam_service.projects().serviceAccounts().keys().create(
                name=f"projects/{self.project_id}/serviceAccounts/{service_account_email}",
                body={'keyAlgorithm': 'KEY_ALG_RSA_2048'}
            ).execute()
            
            # 키 디렉토리 생성
            os.makedirs("keys", exist_ok=True)
            
            # 키 파일 저장
            key_file_path = f"keys/{service_account_id}.json"
            with open(key_file_path, 'w') as f:
                import base64
                key_data = base64.b64decode(key['privateKeyData']).decode('utf-8')
                f.write(key_data)
            
            logger.info(f"✅ Firebase 서비스 계정 키 파일 저장: {key_file_path}")
            return key_file_path
            
        except Exception as e:
            logger.error(f"❌ Firebase 서비스 계정 생성 실패: {e}")
            return None