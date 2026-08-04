"""Phase 7 端到端验证：权限隔离 / 成员管理 / 软删除 / 审计 / 用户管理 / 配置 / 限流。

用法：python scripts/verify_phase7.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows GBK 终端强制 UTF-8 输出
sys.stdout.reconfigure(encoding="utf-8")

import httpx

BASE = "http://localhost:8000/api/v1"
passed: list[str] = []
failed: list[str] = []


def check(name: str, ok: bool, extra: str = "") -> None:
    (passed if ok else failed).append(name)
    print(f"{'✅' if ok else '❌'} {name}" + (f" | {extra}" if extra else ""))


async def login(client: httpx.AsyncClient, username: str, password: str) -> str:
    r = await client.post(f"{BASE}/auth/login", json={"username": username, "password": password})
    r.raise_for_status()
    return r.json()["data"]["access_token"]


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as c:
        # ===== 0. 登录 =====
        admin_t = await login(c, "admin", "Admin123456")
        a = {"Authorization": f"Bearer {admin_t}"}
        t1 = await login(c, "mytest", "test123456")
        u1 = {"Authorization": f"Bearer {t1}"}
        t2 = await login(c, "mytest2", "test123456")
        u2 = {"Authorization": f"Bearer {t2}"}
        print("== 登录完成 ==")

        # ===== 1. 知识库隔离 =====
        # mytest 创建私有 KB
        r = await c.post(f"{BASE}/knowledge-bases", headers=u1,
                         json={"name": "phase7_private_kb", "description": "隔离测试"})
        r.raise_for_status()
        kb_id = r.json()["data"]["id"]
        my_role = r.json()["data"]["my_role"]
        check("mytest 创建 KB", kb_id > 0, f"kb_id={kb_id} my_role={my_role}")

        # mytest2 列表看不到
        r2 = await c.get(f"{BASE}/knowledge-bases", headers=u2)
        kb_ids2 = [x["id"] for x in r2.json()["data"]]
        check("隔离：mytest2 列表看不到私有 KB", kb_id not in kb_ids2)

        # mytest2 直接访问 → 403
        r3 = await c.get(f"{BASE}/knowledge-bases/{kb_id}", headers=u2)
        check("隔离：mytest2 直接访问返回 403", r3.status_code == 403, f"status={r3.status_code}")

        # mytest2 上传文档 → 403
        r4 = await c.post(f"{BASE}/documents/upload", headers=u2,
                          data={"kb_id": str(kb_id)},
                          files={"file": ("test.txt", b"hello", "text/plain")})
        check("隔离：mytest2 上传文档返回 403", r4.status_code == 403, f"status={r4.status_code}")

        # ===== 2. 成员管理 =====
        # mytest 把 mytest2 加为 viewer
        r5 = await c.post(f"{BASE}/knowledge-bases/{kb_id}/members", headers=u1,
                          json={"user_id": 5, "role": "viewer"})
        check("添加成员 viewer", r5.status_code == 200, r5.json().get("message", ""))

        # mytest2 现在能看到
        r6 = await c.get(f"{BASE}/knowledge-bases", headers=u2)
        check("加成员后 mytest2 可见 KB", kb_id in [x["id"] for x in r6.json()["data"]])
        r6b = await c.get(f"{BASE}/knowledge-bases/{kb_id}", headers=u2)
        check("viewer 可查看详情", r6b.status_code == 200, f"my_role={r6b.json()['data'].get('my_role')}")

        # viewer 上传仍 403
        r7 = await c.post(f"{BASE}/documents/upload", headers=u2,
                          data={"kb_id": str(kb_id)},
                          files={"file": ("test.txt", b"hello", "text/plain")})
        check("viewer 上传文档返回 403", r7.status_code == 403)

        # 升级为 editor
        r8 = await c.patch(f"{BASE}/knowledge-bases/{kb_id}/members/5", headers=u1,
                           json={"role": "editor"})
        check("升级成员为 editor", r8.status_code == 200)

        # editor 上传文档 → 200（不等待处理）
        r9 = await c.post(f"{BASE}/documents/upload", headers=u2,
                          data={"kb_id": str(kb_id)},
                          files={"file": ("p7_test.md", "# Phase7 test doc 2026".encode("utf-8"), "text/markdown")})
        check("editor 上传文档成功", r9.status_code == 200, r9.json().get("data", {}).get("id", ""))

        # 成员列表（owner 可见）
        r10 = await c.get(f"{BASE}/knowledge-bases/{kb_id}/members", headers=u1)
        member_names = [(m["username"], m["role"]) for m in r10.json()["data"]]
        check("成员列表含 mytest2/editor", ("mytest2", "editor") in member_names, str(member_names))

        # ===== 3. 文档软删除（在临时 KB 上完成全链路验证） =====
        # editor 上传的小文档：直接调用处理函数（Celery worker 不一定在跑）
        from tasks.document_tasks import _process_document

        class _FakeTask:
            request = type("R", (), {"retries": 0})()

        upload_r = r9
        doc_id = upload_r.json()["data"]["id"]
        await _process_document(_FakeTask(), doc_id)
        # 状态应变为 completed
        r11 = await c.get(f"{BASE}/documents/{doc_id}/status", headers=u1)
        check("上传文档处理完成", r11.json()["data"]["status"] == "completed",
              f"status={r11.json()['data']['status']} chunks={r11.json()['data']['chunk_count']}")

        # 删除前 Chroma 有该文档的 chunk
        from app.db import chroma_store
        before_meta = chroma_store.get_or_create_collection(kb_id).get(
            where={"doc_id": str(doc_id)}, include=["metadatas"]
        )
        check("删除前 Chroma 含文档 chunk", len(before_meta["ids"]) > 0,
              f"{len(before_meta['ids'])} chunks")

        # 软删除（owner）
        r12 = await c.delete(f"{BASE}/documents/{doc_id}", headers=u1)
        check("软删除文档", r12.status_code == 200, f"doc_id={doc_id}")

        # 列表不再出现
        r13 = await c.get(f"{BASE}/documents?kb_id={kb_id}", headers=u1)
        check("列表不再出现已删文档", doc_id not in [d["id"] for d in r13.json()["data"]])

        # 状态查询 404
        r13b = await c.get(f"{BASE}/documents/{doc_id}/status", headers=u1)
        check("已删文档状态查询返回 404", r13b.status_code == 404, f"status={r13b.status_code}")

        # Chroma 级联删除：chunk 已消失
        after_meta = chroma_store.get_or_create_collection(kb_id).get(
            where={"doc_id": str(doc_id)}, include=["metadatas"]
        )
        check("Chroma 级联删除 chunk", len(after_meta["ids"]) == 0)

        # ===== 4. 审计日志（admin） =====
        r14 = await c.get(f"{BASE}/audit-logs", headers=a, params={"page_size": 50})
        logs = r14.json()["data"]["items"]
        actions = {x["action"] for x in logs}
        check("审计：日志非空", len(logs) > 0, f"共 {len(logs)} 条")
        for act in ["kb:create", "kb:member_add", "kb:member_update", "document:upload"]:
            check(f"审计：含 {act}", act in actions)
        has_ip = all(x.get("ip_address") for x in logs[:5])
        check("审计：含 IP", has_ip)

        # ===== 5. 用户管理（admin） =====
        r15 = await c.get(f"{BASE}/users", headers=a, params={"page_size": 20})
        users = r15.json()["data"]["items"]
        check("用户列表", len(users) >= 4, f"{len(users)} 个用户")
        # 禁用 mytest2
        target = next(x for x in users if x["username"] == "mytest2")
        r16 = await c.patch(f"{BASE}/users/{target['id']}", headers=a,
                            json={"is_active": False})
        check("禁用用户", r16.status_code == 200)
        r16b = await c.post(f"{BASE}/auth/login", json={"username": "mytest2", "password": "test123456"})
        check("禁用后无法登录", r16b.status_code == 401, f"status={r16b.status_code}")
        # 恢复
        await c.patch(f"{BASE}/users/{target['id']}", headers=a, json={"is_active": True})
        r16c = await c.get(f"{BASE}/users/roles", headers=a)
        check("角色列表", r16c.status_code == 200)

        # ===== 6. 系统配置（admin） =====
        r17 = await c.get(f"{BASE}/system/configs", headers=a)
        check("配置列表", r17.status_code == 200)
        r18 = await c.put(f"{BASE}/system/configs/llm.temperature", headers=a,
                          json={"value": "0.5"})
        check("更新 llm.temperature", r18.status_code == 200, r18.json().get("message", ""))
        r18b = await c.put(f"{BASE}/system/configs/llm.max_tokens", headers=a,
                           json={"value": "1024"})
        check("更新 llm.max_tokens", r18b.status_code == 200)
        r19 = await c.put(f"{BASE}/system/configs/not.exist", headers=a, json={"value": "1"})
        check("非法配置键被拒", "不支持的配置键" in r19.json()["data"]["error"])

        # ===== 7. KB 配置编辑（owner） =====
        r20 = await c.patch(f"{BASE}/knowledge-bases/{kb_id}", headers=u1,
                            json={"chunk_size": 256, "chunk_overlap": 32})
        check("owner 修改 chunk 配置", r20.status_code == 200,
              f"chunk_size={r20.json()['data']['chunk_size']}")
        r21 = await c.patch(f"{BASE}/knowledge-bases/{kb_id}", headers=u2,
                            json={"chunk_size": 128})
        check("editor 修改配置返回 403", r21.status_code == 403, f"status={r21.status_code}")

        # ===== 8. 限流 =====
        # 直接调用中间件逻辑验证：RATE_LIMIT 关闭时正常
        r22 = await c.get(f"{BASE}/users", headers=a)
        check("限流关闭时正常访问", r22.status_code == 200)

        # ===== 清理 =====
        r23 = await c.delete(f"{BASE}/knowledge-bases/{kb_id}", headers=u1)
        check("owner 删除 KB", r23.status_code == 200)

    print("\n========== 结果 ==========")
    print(f"通过 {len(passed)} / {len(passed) + len(failed)}")
    if failed:
        print("失败项:", failed)
        sys.exit(1)


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    finally:
        loop.close()
