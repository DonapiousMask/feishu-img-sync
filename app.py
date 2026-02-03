import streamlit as st
import requests
import time
import re

# ================= 默认配置 =================
DEFAULT_APP_ID = "cli_a9f33af0a238dbd3"
DEFAULT_APP_SECRET = "I3Cko6T9AI3AIZEnXVJ6Rhsl46KiiClg"

st.set_page_config(page_title="飞书图片自动搬运工", page_icon="🖼️")

def get_tenant_access_token(app_id, app_secret):
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    try:
        res = requests.post(url, json={"app_id": app_id, "app_secret": app_secret})
        res_data = res.json()
        if res_data.get("code") == 0:
            return res_data.get("tenant_access_token")
        return None
    except:
        return None

def upload_image(token, app_token, img_url):
    try:
        resp = requests.get(img_url, timeout=15)
        if resp.status_code != 200: return None
        img_content = resp.content
        
        upload_url = "https://open.feishu.cn/open-apis/drive/v1/medias/upload_all"
        headers = {"Authorization": f"Bearer {token}"}
        form_data = {
            'file_name': 'main_img.jpg',
            'parent_type': 'bitable_image',
            'parent_node': app_token,
            'size': str(len(img_content))
        }
        files = {'file': img_content}
        res = requests.post(upload_url, headers=headers, data=form_data, files=files).json()
        return res.get("data", {}).get("file_token")
    except:
        return None

# --- UI 界面 ---
st.title("🖼️ 飞书多维表格图片自动同步")
st.markdown("---")

with st.sidebar:
    st.header("🔑 凭证设置")
    app_id = st.text_input("App ID", value=DEFAULT_APP_ID)
    app_secret = st.text_input("App Secret", value=DEFAULT_APP_SECRET, type="password")
    st.info("提示：请务必在飞书表格中将此应用添加为协作者。")

# 输入表格链接
feishu_url = st.text_input("🔗 粘贴飞书表格完整链接", placeholder="https://ocn3pj3qq88x.feishu.cn/base/...")

col1, col2 = st.columns(2)
with col1:
    source_col = st.text_input("🔗 源链接列名", value="主图链接")
with col2:
    target_col = st.text_input("📁 目标附件列名", value="产品图片")

if st.button("🚀 开始同步数据", type="primary"):
    if not feishu_url:
        st.error("请输入表格链接！")
    else:
        # 解析 URL
        try:
            app_token = re.findall(r"base/([a-zA-Z0-9]+)", feishu_url)[0]
            table_id = re.findall(r"table=([a-zA-Z0-9]+)", feishu_url)[0]
        except:
            st.error("链接解析失败！请确保链接包含 base/ 和 table=")
            st.stop()

        token = get_tenant_access_token(app_id, app_secret)
        if not token:
            st.error("授权失败！请检查 App ID 和 Secret")
        else:
            st.success("✅ 授权成功，正在后台检索数据...")
            
            headers = {"Authorization": f"Bearer {token}"}
            page_token = ""
            total_success = 0
            total_scanned = 0
            
            # 使用 st.empty() 创建动态更新区域
            progress_bar = st.progress(0)
            status_area = st.empty()
            log_area = st.empty()

            # 开始分页循环
            while True:
                list_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
                params = {"page_size": 100, "page_token": page_token}
                try:
                    res = requests.get(list_url, headers=headers, params=params).json()
                    if res.get("code") != 0:
                        st.error(f"读取报错: {res.get('msg')}")
                        break
                    
                    data = res.get("data", {})
                    records = data.get("items", [])
                    if not records: break

                    for rec in records:
                        rid = rec['record_id']
                        fields = rec['fields']
                        img_url = fields.get(source_col)
                        
                        if isinstance(img_url, dict): img_url = img_url.get('text', '')

                        # 核心逻辑：断点续传（目标列没图才处理）
                        if img_url and not fields.get(target_col):
                            f_token = upload_image(token, app_token, img_url)
                            if f_token:
                                update_url = f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/{rid}"
                                requests.put(update_url, headers=headers, json={"fields": {target_col: [{"file_token": f_token}]}})
                                total_success += 1
                                
                            # 每成功 1 条更新一次状态
                            status_area.write(f"📈 正在处理中... 当前成功搬运: **{total_success}** 张图片")
                            time.sleep(0.3)
                        
                        total_scanned += 1
                        # 仅在日志区域更新扫描进度，避免界面疯狂刷新导致卡顿
                        if total_scanned % 50 == 0:
                            log_area.caption(f"已扫描 {total_scanned} 行数据...")

                    page_token = data.get("page_token", "")
                    if not data.get("has_more"): break
                except Exception as e:
                    st.warning(f"由于网络抖动，正在重试... 错误: {e}")
                    time.sleep(2)
                    continue

            st.balloons()

            st.success(f"🏁 任务圆满完成！本次共成功搬运 {total_success} 张图片。")

