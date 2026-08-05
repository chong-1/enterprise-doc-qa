"""API 集成测试：覆盖认证、知识库、文档、问答、对话、用户管理、审计、配置。

运行前确保：FastAPI 在 localhost:8000 运行，Redis 在 localhost:6379 运行。
用法：pytest tests/test_api_integration.py -v -s
"""

import pytest
import httpx

BASE = "http://localhost:8000/api/v1"

# ====== 测试数据 ======
TEST_USER = "p9test_user"
TEST_EMAIL = "p9test@example.com"
TEST_PASS = "p9test123"


@pytest.fixture(scope="module")
def client():
    """共享 httpx 客户端（module 级复用 TCP 连接）。"""
    with httpx.Client(timeout=120) as c:
        yield c


@pytest.fixture(scope="module")
def admin_token(client):
    """管理员 token。"""
    r = client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "Admin123456"})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


@pytest.fixture(scope="module")
def user_token(client):
    """测试用户 token（注册或登录）。"""
    # 尝试登录
    r = client.post(f"{BASE}/auth/login", json={"username": TEST_USER, "password": TEST_PASS})
    if r.status_code == 200:
        return r.json()["data"]["access_token"]
    # 注册
    r2 = client.post(f"{BASE}/auth/register", json={"username": TEST_USER, "email": TEST_EMAIL, "password": TEST_PASS})
    if r2.status_code == 200:
        r3 = client.post(f"{BASE}/auth/login", json={"username": TEST_USER, "password": TEST_PASS})
        return r3.json()["data"]["access_token"]
    pytest.fail(f"Cannot get user token: {r2.text}")


# ===================================================================
# 认证
# ===================================================================
class TestAuth:
    def test_login_success(self, client):
        r = client.post(f"{BASE}/auth/login", json={"username": "mytest", "password": "test123456"})
        assert r.status_code == 200
        assert "access_token" in r.json()["data"]

    def test_login_wrong_password(self, client):
        r = client.post(f"{BASE}/auth/login", json={"username": "mytest", "password": "wrong"})
        assert r.status_code == 401

    def test_register_duplicate(self, client):
        r = client.post(f"{BASE}/auth/register", json={"username": "mytest", "email": "dup@example.com", "password": "123456"})
        assert r.status_code == 409

    def test_me_endpoint(self, client, user_token):
        r = client.get(f"{BASE}/users/me", headers=auth(user_token))
        assert r.status_code == 200
        assert r.json()["data"]["username"] == TEST_USER

    def test_refresh_token(self, client, admin_token):
        r = client.post(f"{BASE}/auth/login", json={"username": "admin", "password": "Admin123456"})
        refresh = r.json()["data"]["refresh_token"]
        r2 = client.post(f"{BASE}/auth/refresh", json={"refresh_token": refresh})
        assert r2.status_code == 200
        assert "access_token" in r2.json()["data"]


# ===================================================================
# 知识库
# ===================================================================
class TestKnowledgeBases:
    kb_id = None

    def test_create(self, client, user_token):
        r = client.post(f"{BASE}/knowledge-bases", headers=auth(user_token),
                        json={"name": "p9test_kb", "description": "集成测试用", "is_public": False})
        assert r.status_code == 200
        TestKnowledgeBases.kb_id = r.json()["data"]["id"]
        assert r.json()["data"]["my_role"] == "owner"

    def test_list_contains_new(self, client, user_token):
        r = client.get(f"{BASE}/knowledge-bases", headers=auth(user_token))
        assert r.status_code == 200
        ids = [k["id"] for k in r.json()["data"]]
        assert TestKnowledgeBases.kb_id in ids

    def test_detail(self, client, user_token):
        r = client.get(f"{BASE}/knowledge-bases/{TestKnowledgeBases.kb_id}", headers=auth(user_token))
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "p9test_kb"

    def test_update_as_owner(self, client, user_token):
        r = client.patch(f"{BASE}/knowledge-bases/{TestKnowledgeBases.kb_id}", headers=auth(user_token),
                         json={"chunk_size": 256, "name": "p9test_kb_updated"})
        assert r.status_code == 200
        assert r.json()["data"]["chunk_size"] == 256

    def test_isolation_other_user_cannot_see(self, client, admin_token):
        """admin 的私有 KB 不应出现在 mytest 列表中。"""
        # 用 mytest 登录
        r1 = client.post(f"{BASE}/auth/login", json={"username": "mytest", "password": "test123456"})
        t = r1.json()["data"]["access_token"]
        r2 = client.get(f"{BASE}/knowledge-bases", headers=auth(t))
        ids = [k["id"] for k in r2.json()["data"]]
        assert TestKnowledgeBases.kb_id not in ids  # mytest 不是 p9test_kb 的成员

    def test_member_management(self, client, user_token):
        """添加/查看/修改/移除成员。"""
        kb = TestKnowledgeBases.kb_id
        # 加 mytest 为 viewer
        r = client.post(f"{BASE}/knowledge-bases/{kb}/members", headers=auth(user_token),
                        json={"user_id": 4, "role": "viewer"})
        assert r.status_code == 200
        # 列表
        r2 = client.get(f"{BASE}/knowledge-bases/{kb}/members", headers=auth(user_token))
        members = {m["user_id"]: m["role"] for m in r2.json()["data"]}
        assert 4 in members and members[4] == "viewer"
        # 升级
        r3 = client.patch(f"{BASE}/knowledge-bases/{kb}/members/4", headers=auth(user_token),
                          json={"role": "editor"})
        assert r3.status_code == 200
        # 移除
        r4 = client.delete(f"{BASE}/knowledge-bases/{kb}/members/4", headers=auth(user_token))
        assert r4.status_code == 200


# ===================================================================
# 文档
# ===================================================================
class TestDocuments:
    doc_id = None

    def test_upload(self, client, user_token):
        kb = TestKnowledgeBases.kb_id
        r = client.post(f"{BASE}/documents/upload", headers=auth(user_token),
                        data={"kb_id": str(kb)},
                        files={"file": ("p9_test.md", "# P9 Test\nHello integration test.", "text/markdown")})
        assert r.status_code == 200, r.text
        TestDocuments.doc_id = r.json()["data"]["id"]
        assert r.json()["data"]["status"] == "pending"

    def test_list(self, client, user_token):
        kb = TestKnowledgeBases.kb_id
        r = client.get(f"{BASE}/documents", headers=auth(user_token), params={"kb_id": kb})
        assert r.status_code == 200
        ids = [d["id"] for d in r.json()["data"]]
        assert TestDocuments.doc_id in ids

    def test_status(self, client, user_token):
        r = client.get(f"{BASE}/documents/{TestDocuments.doc_id}/status", headers=auth(user_token))
        assert r.status_code == 200
        assert r.json()["data"]["status"] in ("pending", "processing", "completed", "failed")

    def test_delete_soft(self, client, user_token):
        r = client.delete(f"{BASE}/documents/{TestDocuments.doc_id}", headers=auth(user_token))
        assert r.status_code == 200
        # 再查返回 404
        r2 = client.get(f"{BASE}/documents/{TestDocuments.doc_id}/status", headers=auth(user_token))
        assert r2.status_code == 404


# ===================================================================
# 问答
# ===================================================================
class TestQA:
    conv_id = None

    def test_ask_non_stream(self, client, user_token):
        kb = TestKnowledgeBases.kb_id
        r = client.post(f"{BASE}/qa/{kb}", headers=auth(user_token),
                        json={"question": "test question", "stream": False})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert len(data["answer"]) > 0
        assert data["conversation_id"] is not None
        TestQA.conv_id = data["conversation_id"]

    def test_ask_without_permission(self, client, user_token):
        """mytest2 无 p9test_kb 权限，问答应 403。"""
        # 登录 mytest2（确保它不是该 KB 的成员）
        r1 = client.post(f"{BASE}/auth/login", json={"username": "mytest2", "password": "test123456"})
        t = r1.json()["data"]["access_token"]
        # 先确保 mytest2 被移出（忽略 404——可能本来就不是成员）
        client.delete(f"{BASE}/knowledge-bases/{TestKnowledgeBases.kb_id}/members/5", headers=auth(user_token))
        r2 = client.post(f"{BASE}/qa/{TestKnowledgeBases.kb_id}", headers=auth(t),
                         json={"question": "x", "stream": False})
        assert r2.status_code == 403, f"Expected 403, got {r2.status_code}: {r2.text}"

    def test_agent_mode(self, client, user_token):
        kb = TestKnowledgeBases.kb_id
        r = client.post(f"{BASE}/qa/{kb}", headers=auth(user_token),
                        json={"question": "hello", "stream": False, "agent_mode": True,
                              "conversation_id": TestQA.conv_id})
        assert r.status_code == 200, r.text
        assert len(r.json()["data"]["answer"]) > 0


# ===================================================================
# 对话
# ===================================================================
class TestConversations:
    def test_list(self, client, user_token):
        r = client.get(f"{BASE}/conversations", headers=auth(user_token))
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        ids = [c["id"] for c in items]
        assert TestQA.conv_id in ids

    def test_detail(self, client, user_token):
        r = client.get(f"{BASE}/conversations/{TestQA.conv_id}", headers=auth(user_token))
        assert r.status_code == 200
        assert "title" in r.json()["data"]

    def test_messages(self, client, user_token):
        r = client.get(f"{BASE}/conversations/{TestQA.conv_id}/messages", headers=auth(user_token))
        assert r.status_code == 200
        msgs = r.json()["data"]["items"]
        assert len(msgs) >= 2  # user + assistant
        roles = [m["role"] for m in msgs]
        assert "user" in roles
        assert "assistant" in roles


# ===================================================================
# 用户管理（管理员）
# ===================================================================
class TestUserManagement:
    def test_list(self, client, admin_token):
        r = client.get(f"{BASE}/users", headers=auth(admin_token))
        assert r.status_code == 200
        assert r.json()["data"]["total"] >= 4

    def test_search(self, client, admin_token):
        r = client.get(f"{BASE}/users", headers=auth(admin_token), params={"keyword": "admin"})
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert any(u["username"] == "admin" for u in items)

    def test_forbidden_for_normal_user(self, client, user_token):
        r = client.get(f"{BASE}/users", headers=auth(user_token))
        assert r.status_code == 403

    def test_update_user(self, client, admin_token):
        # 禁用 p9test_user 再恢复
        r = client.patch(f"{BASE}/users/4", headers=auth(admin_token), json={"is_active": False})
        assert r.status_code == 200
        r2 = client.patch(f"{BASE}/users/4", headers=auth(admin_token), json={"is_active": True})
        assert r2.status_code == 200


# ===================================================================
# 审计日志（管理员）
# ===================================================================
class TestAuditLogs:
    def test_list(self, client, admin_token):
        r = client.get(f"{BASE}/audit-logs", headers=auth(admin_token), params={"page_size": 20})
        assert r.status_code == 200
        assert r.json()["data"]["total"] > 0

    def test_filter_by_action(self, client, admin_token):
        r = client.get(f"{BASE}/audit-logs", headers=auth(admin_token),
                       params={"action": "kb:create", "page_size": 10})
        assert r.status_code == 200
        for item in r.json()["data"]["items"]:
            assert item["action"] == "kb:create"

    def test_forbidden_for_normal(self, client, user_token):
        r = client.get(f"{BASE}/audit-logs", headers=auth(user_token))
        assert r.status_code == 403


# ===================================================================
# 系统配置（管理员）
# ===================================================================
class TestSystemConfig:
    def test_list(self, client, admin_token):
        r = client.get(f"{BASE}/system/configs", headers=auth(admin_token))
        assert r.status_code == 200
        assert "supported_keys" in r.json()["data"]

    def test_update_and_read_back(self, client, admin_token):
        r = client.put(f"{BASE}/system/configs/llm.temperature", headers=auth(admin_token),
                       json={"value": "0.7"})
        assert r.status_code == 200
        r2 = client.get(f"{BASE}/system/configs", headers=auth(admin_token))
        configs = {c["key"]: c["value"] for c in r2.json()["data"]["configs"]}
        assert configs.get("llm.temperature") == "0.7"

    def test_invalid_key(self, client, admin_token):
        r = client.put(f"{BASE}/system/configs/fake.key", headers=auth(admin_token),
                       json={"value": "1"})
        assert "不支持的配置键" in str(r.json())


# ===================================================================
# 清理
# ===================================================================
class TestCleanup:
    def test_delete_kb_cascades(self, client, user_token):
        r = client.delete(f"{BASE}/knowledge-bases/{TestKnowledgeBases.kb_id}", headers=auth(user_token))
        assert r.status_code == 200
        # 确认已删
        r2 = client.get(f"{BASE}/knowledge-bases/{TestKnowledgeBases.kb_id}", headers=auth(user_token))
        # 不是 owner 也不是成员后，应该 403 或 404（取决于 check_kb_access 逻辑：先查 kb 是否存在）
        # 删了后 kb 不存在，check_kb_access 里 kb is None → 404
        assert r2.status_code in (403, 404)


# ====== 工具 ======
def auth(token):
    return {"Authorization": f"Bearer {token}"}
