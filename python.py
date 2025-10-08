import streamlit as st
import pandas as pd
# --- LƯU Ý: Đảm bảo bạn đã cài đặt google-generativeai ---
# --- pip install google-generativeai ---
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính & Chatbot AI 📊")

# --- Hàm tính toán chính (Sử dụng Caching để Tối ưu hiệu suất) ---
@st.cache_data
def process_financial_data(df):
    """Thực hiện các phép tính Tăng trưởng và Tỷ trọng."""

    # Đảm bảo các giá trị là số để tính toán
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 1. Tính Tốc độ Tăng trưởng
    # Dùng .replace(0, 1e-9) cho Series Pandas để tránh lỗi chia cho 0
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tính Tỷ trọng theo Tổng Tài sản
    # Lọc chỉ tiêu "TỔNG CỘNG TÀI SẢN"
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]

    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    # Xử lý trường hợp chia cho 0
    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    # Tính tỷ trọng với mẫu số đã được xử lý
    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100

    return df

# --- Hàm gọi API Gemini cho Phân Tích Tổng Quan (Code gốc của bạn) ---
def get_ai_analysis(data_for_ai, api_key):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.

        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """

        response = model.generate_content(prompt)
        return response.text

    except google_exceptions.PermissionDenied:
        return "Lỗi: Khóa API không hợp lệ hoặc đã hết hạn. Vui lòng kiểm tra lại."
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"

# --- HÀM MỚI: Gọi API Gemini cho Chatbot ---
def get_chatbot_response(api_key, question, chat_history, financial_data_str):
    """Gửi câu hỏi, lịch sử chat và dữ liệu đến Gemini để nhận câu trả lời."""
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash-latest')

        # System prompt: Hướng dẫn vai trò và ngữ cảnh cho AI
        system_prompt = f"""
        Bạn là một trợ lý tài chính AI, chuyên trả lời các câu hỏi dựa trên dữ liệu từ một file Excel đã được tải lên.
        Dưới đây là toàn bộ dữ liệu đã được xử lý từ file đó. Chỉ sử dụng thông tin này để trả lời.
        Nếu câu hỏi của người dùng không liên quan đến dữ liệu này, hãy trả lời một cách lịch sự rằng bạn không thể trả lời câu hỏi nằm ngoài phạm vi dữ liệu tài chính được cung cấp.
        Không bịa đặt thông tin.

        --- DỮ LIỆU TÀI CHÍNH ---
        {financial_data_str}
        --- KẾT THÚC DỮ LIỆU ---
        """

        # Xây dựng lịch sử trò chuyện cho API
        conversation_history = []
        for message in chat_history:
            role = 'user' if message['role'] == 'user' else 'model'
            conversation_history.append({'role': role, 'parts': [message['content']]})

        # Bắt đầu một phiên chat mới với lịch sử và system prompt
        chat = model.start_chat(history=conversation_history)
        response = chat.send_message(question, system_instruction=system_prompt)

        return response.text

    except google_exceptions.PermissionDenied:
        return "Lỗi: Khóa API không hợp lệ hoặc đã hết hạn. Vui lòng kiểm tra lại."
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"

# --- Giao diện chính ---

# Chức năng 1: Tải File
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (Định dạng: Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file)
        df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau'] # Đảm bảo tên cột nhất quán

        # Lưu trữ dataframe đã xử lý vào session_state để chatbot có thể truy cập
        st.session_state.df_processed = process_financial_data(df_raw.copy())

        if "df_processed" in st.session_state:
            df_processed = st.session_state.df_processed
            # Chức năng 2 & 3: Hiển thị Kết quả
            st.subheader("2. Tốc độ Tăng trưởng & 3. Tỷ trọng Cơ cấu Tài sản")
            st.dataframe(df_processed.style.format({
                'Năm trước': '{:,.0f}',
                'Năm sau': '{:,.0f}',
                'Tốc độ tăng trưởng (%)': '{:.2f}%',
                'Tỷ trọng Năm trước (%)': '{:.2f}%',
                'Tỷ trọng Năm sau (%)': '{:.2f}%'
            }), use_container_width=True)

            # Chức năng 4: Tính Chỉ số Tài chính
            st.subheader("4. Các Chỉ số Tài chính Cơ bản")
            try:
                # Lọc giá trị
                tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]
                no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                # Tính toán, xử lý chia cho 0
                thanh_toan_hien_hanh_N = tsnh_n / no_ngan_han_N if no_ngan_han_N != 0 else 0
                thanh_toan_hien_hanh_N_1 = tsnh_n_1 / no_ngan_han_N_1 if no_ngan_han_N_1 != 0 else 0

                col1, col2 = st.columns(2)
                with col1:
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm trước)",
                        value=f"{thanh_toan_hien_hanh_N_1:.2f} lần"
                    )
                with col2:
                    st.metric(
                        label="Chỉ số Thanh toán Hiện hành (Năm sau)",
                        value=f"{thanh_toan_hien_hanh_N:.2f} lần",
                        delta=f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}"
                    )
                # Lưu chỉ số để AI sử dụng
                st.session_state.current_ratio_n_1 = f"{thanh_toan_hien_hanh_N_1}"
                st.session_state.current_ratio_n = f"{thanh_toan_hien_hanh_N}"

            except (IndexError, KeyError):
                st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số thanh toán.")
                st.session_state.current_ratio_n_1 = "N/A"
                st.session_state.current_ratio_n = "N/A"

            # Chức năng 5: Nhận xét AI
            st.subheader("5. Nhận xét Tình hình Tài chính (AI)")
            if st.button("Yêu cầu AI Phân tích Tổng quan"):
                api_key = st.secrets.get("GEMINI_API_KEY")
                if api_key:
                    with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                        data_for_ai = pd.DataFrame({
                            'Chỉ tiêu': ['Toàn bộ Bảng phân tích', 'Thanh toán hiện hành (N-1)', 'Thanh toán hiện hành (N)'],
                            'Giá trị': [
                                st.session_state.df_processed.to_markdown(index=False),
                                st.session_state.current_ratio_n_1,
                                st.session_state.current_ratio_n
                            ]
                        }).to_markdown(index=False)
                        ai_result = get_ai_analysis(data_for_ai, api_key)
                        st.info(ai_result)
                else:
                    st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình 'GEMINI_API_KEY' trong Streamlit Secrets.")

            # --- CHỨC NĂNG 6: CHATBOT ---
            st.divider()
            st.subheader("6. Chat với Trợ lý Tài chính AI")
            st.caption("Bạn có thể đặt câu hỏi chi tiết về dữ liệu vừa tải lên.")

            # Khởi tạo lịch sử chat
            if "messages" not in st.session_state:
                st.session_state.messages = []

            # Hiển thị các tin nhắn cũ
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

            # Nhận input từ người dùng
            if prompt := st.chat_input("Ví dụ: 'Tài sản dài hạn đã thay đổi như thế nào?'"):
                api_key = st.secrets.get("GEMINI_API_KEY")
                if not api_key:
                    st.error("Lỗi: Không tìm thấy Khóa API để bắt đầu chat. Vui lòng cấu hình 'GEMINI_API_KEY' trong Streamlit Secrets.")
                else:
                    # Thêm tin nhắn của người dùng vào lịch sử và hiển thị
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    with st.chat_message("user"):
                        st.markdown(prompt)

                    # Tạo và hiển thị phản hồi từ AI
                    with st.chat_message("assistant"):
                        with st.spinner("AI đang soạn câu trả lời..."):
                            financial_data_str = st.session_state.df_processed.to_markdown()
                            response = get_chatbot_response(
                                api_key,
                                prompt,
                                st.session_state.messages,
                                financial_data_str
                            )
                            st.markdown(response)
                    # Thêm phản hồi của AI vào lịch sử
                    st.session_state.messages.append({"role": "assistant", "content": response})

    except ValueError as ve:
        st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
    except Exception as e:
        st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")

else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")

