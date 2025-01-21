import re 
import time
import math
import smtplib
from email.mime.text import MIMEText

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def send_email(subject, content, to_email):
    # 目前仅支持Gmail邮箱
    smtp_server = 'smtp.gmail.com'
    smtp_port = 587
    ### 替换为你的Gmail地址
    sender_email = 'replace_here@gmail.com'
    ### 替换为你的Google App Password，需要先启用Google账户中的两步认证
    sender_password = 'replace_here'

    msg = MIMEText(content, 'plain', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = to_email

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo() 
            server.starttls()
            server.ehlo() 
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, msg.as_string())
            print("邮件发送成功！")
    except Exception as e:
        print(f"邮件发送失败：{e}")


def get_total_apartments(driver):
    """
    在首页中，通过精确选择器 span.f2-widget.Objektsummering.Lagenheter
    来获取可用房源总数。如果为空，则等待几秒再重试。
    返回整数房源数，如 63。若始终无法获取，返回 0。
    """
    wait = WebDriverWait(driver, 20)

    try:
        cookie_btn = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button#cookie-accept-button"))
        )
        cookie_btn.click()
        print("已点击 Cookie 同意按钮")
    except:
        print("没有发现 Cookie 弹窗，或无法点击，跳过此步")

    span_selector = "span.f2-widget.Objektsummering.Lagenheter"
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, span_selector)))
    except Exception as e:
        print("等待 span.f2-widget.Objektsummering.Lagenheter 出现超时:", e)
        return 0

    for attempt in range(3):
        span_el = driver.find_element(By.CSS_SELECTOR, span_selector)
        raw_text = span_el.text.strip()
        print(f"Raw summary text = '{raw_text}' (attempt {attempt+1})")

        if raw_text:
            match = re.search(r"(\d+)", raw_text)
            if match:
                total_apt = int(match.group(1))
                print("成功获取可用房源数量:", total_apt)
                return total_apt
            else:
                print("未能提取到数字，原始文本 =", raw_text)
                return 0
        else:
            print("该元素文本仍为空，再等2秒重试...")
            time.sleep(2)

    print("文本一直为空，获取房源数失败")
    return 0


def check_apartments():
    """
    从首页获取房源总数 -> 计算总页数 -> 逐页抓取。
    """
    driver = webdriver.Chrome()
    base_url = "https://sssb.se/en/looking-for-housing/apply-for-apartment/available-apartments/"
    per_page = 10

    try:
        driver.get(base_url)
        total_apt = get_total_apartments(driver)
        if total_apt <= 0:
            print("总房源数为0，或页面结构变动，停止爬取。")
            driver.quit()
            return

        total_pages = math.ceil(total_apt / per_page)
        print(f"估算总共 {total_pages} 页。")

    except Exception as e:
        print("初次获取总房源数量失败：", e)
        driver.quit()
        return

    driver.quit()

    all_apartments_info = []
    for page_index in range(total_pages):
        pagination_value = page_index
        page_url = (
            f"https://sssb.se/en/looking-for-housing/apply-for-apartment/available-apartments/"
            f"?pagination={pagination_value}&paginationantal={per_page}"
        )
        print(f"\n开始抓取第{page_index+1}页: {page_url}")

        driver = webdriver.Chrome()
        driver.get(page_url)
        try:
            wait = WebDriverWait(driver, 15)

            try:
                cookie_btn2 = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button#cookie-accept-button"))
                )
                cookie_btn2.click()
                print("(分页)已点击 Cookie 同意按钮")
            except:
                pass

            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.media")))
            time.sleep(2)

            listings = driver.find_elements(By.CSS_SELECTOR, "div.media")
            print(f"本页抓到 {len(listings)} 条房源")

            for listing in listings:
                try:
                    title_elem = listing.find_element(By.CSS_SELECTOR, "h3.ObjektTyp a")
                    title = title_elem.text.strip()

                    try:
                        region_elem = listing.find_element(By.CSS_SELECTOR, "dd.ObjektOmrade a")
                        region = region_elem.text.strip()
                    except:
                        try:
                            region_elem = listing.find_element(By.CSS_SELECTOR, "dd.ObjektOmrade")
                            region = region_elem.text.strip()
                        except:
                            region = "N/A"

                    try:
                        price_elem = listing.find_element(By.CSS_SELECTOR, "dd.ObjektHyra")
                        price = price_elem.text.strip()
                    except:
                        price = "N/A"

                    all_apartments_info.append({
                        "title": title,
                        "region": region,
                        "price": price
                    })

                except Exception as e:
                    print("房源信息提取失败：", e)

        except Exception as e:
            print("抓取该页失败：", e)

        finally:
            driver.quit()

    print(f"\n共抓取到 {len(all_apartments_info)} 条房源信息。")
    if not all_apartments_info:
        print("没有任何房源数据。")
        return

    print("-------- 所有房源列表 --------")
    for apt in all_apartments_info:
        print(f"标题: {apt['title']} | 价格: {apt['price']} | 区域: {apt['region']}")
    print("--------------------------------")

    matched_apts = []
    ### 地区：修改为你希望监控的房源所在地区，注意使用英文小写
    target_regions = ["strix", "pax", "kungshamra", "lappkärrsberget", "marieberg"]
    for apt in all_apartments_info:
        t_lower = apt['title'].lower()
        r_lower = apt['region'].lower()
        ### 住房类型：修改为房源名称中的关键词，例如1 room, corridor, etc.
        if (("corridor" in t_lower) and any(x in r_lower for x in target_regions)):
            matched_apts.append(apt)

    if matched_apts:
        email_content = []
        for apt in matched_apts:
            item_str = (
                f"标题: {apt['title']}\n"
                f"价格: {apt['price']}\n"
                f"区域: {apt['region']}\n"
                # f"链接: {base_url}\n\n"
            )
            email_content.append(item_str)

        final_content = "以下房源符合筛选条件：\n\n" + "\n\n".join(email_content)
        print("-------- 符合筛选条件的房源列表 --------")
        print(final_content)
        ### 修改为你希望接收消息的邮箱地址
        send_email("SSSB新房源通知", final_content, "replace_here@replace_here.com")

    else:
        print("无符合条件的房源，无需发送邮件。")


def main():
    print("开始监控房源信息...")
    while True:
        check_apartments()
        ### 默认每天执行一次，可自行修改
        time.sleep(86400)

if __name__ == "__main__":
    main()
