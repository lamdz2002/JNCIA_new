import streamlit as st
import docx
import re
import sys
import os
import random
import time
import json
from streamlit.web import cli as stcli

# Tên file để lưu trữ dữ liệu câu hỏi
DB_FILE = "quiz_database.json"

# Cấu hình trang web
st.set_page_config(page_title="App Ôn Thi Trắc Nghiệm", layout="centered")

def parse_docx(file):
    """
    Hàm đọc file docx và chuyển đổi thành danh sách câu hỏi.
    """
    doc = docx.Document(file)
    questions = []
    
    current_q = {
        "question": "",
        "options": [],
        "correct_answer": "",
        "explanation": ""
    }
    
    p_question_start = re.compile(r"^Question\s+\d+.*", re.IGNORECASE)
    p_option_start = re.compile(r"^([A-D])\.(.*)", re.DOTALL)
    p_correct = re.compile(r"Correct Answer:\s*([A-D]+)", re.IGNORECASE)
    p_explanation = re.compile(r"^\*\s*Explanation", re.IGNORECASE)

    state = 'NONE' 

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        if p_question_start.match(text):
            if current_q['question'] and current_q['options'] and current_q['correct_answer']:
                questions.append(current_q)
            current_q = {"question": "", "options": [], "correct_answer": "", "explanation": ""}
            state = 'QUESTION'
            continue

        match_correct = p_correct.search(text)
        if match_correct:
            current_q['correct_answer'] = match_correct.group(1).upper()
            state = 'FINISHED'
            continue

        if p_explanation.match(text):
            state = 'EXPLANATION'
            continue

        match_option = p_option_start.match(text)
        if match_option:
            opt_char = match_option.group(1)
            opt_content = match_option.group(2).strip()
            full_option = f"{opt_char}. {opt_content}"
            current_q['options'].append(full_option)
            state = 'OPTION'
            continue

        if state == 'QUESTION':
            if current_q['question']:
                current_q['question'] += "\n" + text
            else:
                current_q['question'] = text
        elif state == 'OPTION':
            if current_q['options']:
                current_q['options'][-1] += " " + text
        elif state == 'EXPLANATION':
            current_q['explanation'] += text + "\n"

    if current_q['question'] and current_q['options'] and current_q['correct_answer']:
        questions.append(current_q)
        
    return questions

def save_data_to_disk(data):
    """Lưu dữ liệu vào file JSON"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"Lỗi khi lưu dữ liệu: {e}")
        return False

def load_data_from_disk():
    """Đọc dữ liệu từ file JSON nếu có"""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def reset_quiz():
    st.session_state.current_index = 0
    st.session_state.score = 0
    st.session_state.user_answers = {}
    st.session_state.toast_msg = None

def calculate_score():
    """Tính toán lại điểm số dựa trên user_answers"""
    curr_score = 0
    for k, v in st.session_state.user_answers.items():
        if k < len(st.session_state.quiz_data):
            k_correct = sorted(list(st.session_state.quiz_data[k]['correct_answer'].strip()))
            if v == k_correct:
                curr_score += 1
    st.session_state.score = curr_score

def main():
    st.title("📝 Ứng Dụng Ôn Thi Trắc Nghiệm")
    
    # --- PHẦN KHỞI TẠO DỮ LIỆU ---
    if 'full_data' not in st.session_state:
        saved_data = load_data_from_disk()
        if saved_data:
            st.session_state.full_data = saved_data
        else:
            st.session_state.full_data = []

    if 'quiz_data' not in st.session_state:
        st.session_state.quiz_data = [] 
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0
    if 'score' not in st.session_state:
        st.session_state.score = 0
    if 'user_answers' not in st.session_state:
        st.session_state.user_answers = {}
    
    # Biến để hiện thông báo (Toast) khi chuyển câu
    if 'toast_msg' not in st.session_state:
        st.session_state.toast_msg = None
    
    if 'processed_file' not in st.session_state:
        st.session_state.processed_file = None

    # --- SIDEBAR ---
    with st.sidebar:
        st.header("1. Điều khiển")
        if st.button("🛑 Tắt ứng dụng (Thoát)", type="primary"):
            st.warning("Đã tắt server! Bạn có thể đóng tab trình duyệt này.")
            time.sleep(1)
            os._exit(0)

        st.divider()
        st.header("2. Quản lý dữ liệu")
        
        if st.session_state.full_data:
            st.success(f"Đang có: {len(st.session_state.full_data)} câu hỏi")
            if st.button("🗑️ Xóa tất cả dữ liệu gốc"):
                if os.path.exists(DB_FILE):
                    os.remove(DB_FILE)
                st.session_state.full_data = []
                st.session_state.quiz_data = []
                st.session_state.processed_file = None 
                reset_quiz()
                st.rerun()
        else:
            st.warning("Chưa có dữ liệu câu hỏi.")

        uploaded_file = st.file_uploader("Nạp thêm/Thay thế file Word (.docx)", type=['docx'])

        if st.session_state.full_data:
            st.divider()
            st.header("3. Cấu hình bài thi")
            mode = st.radio("Chọn chế độ:", ["Ôn tập (Tất cả)", "Thi thử (Random)"])
            
            if mode == "Thi thử (Random)":
                total_qs = len(st.session_state.full_data)
                num_q = st.number_input(
                    f"Số câu hỏi (Max: {total_qs})", 
                    min_value=1, 
                    max_value=total_qs, 
                    value=min(20, total_qs)
                )
                if st.button("Tạo đề thi mới 🎲"):
                    st.session_state.quiz_data = random.sample(st.session_state.full_data, num_q)
                    reset_quiz()
                    st.success(f"Đã tạo đề mới gồm {num_q} câu!")
                    st.rerun()
            else: 
                if st.button("Bắt đầu ôn tập 📖"):
                    st.session_state.quiz_data = st.session_state.full_data
                    reset_quiz()
                    st.rerun()
            
            if st.session_state.quiz_data:
                st.info(f"Đang làm: {len(st.session_state.quiz_data)} câu")

    # --- XỬ LÝ UPLOAD FILE ---
    if uploaded_file is not None:
        if st.session_state.processed_file != uploaded_file.name:
            with st.spinner("Đang xử lý và lưu dữ liệu..."):
                try:
                    data = parse_docx(uploaded_file)
                    if not data:
                        st.error("File không đúng định dạng!")
                    else:
                        st.session_state.full_data = data
                        save_data_to_disk(data)
                        st.session_state.processed_file = uploaded_file.name
                        st.session_state.quiz_data = data
                        reset_quiz()
                        st.success(f"Đã lưu {len(data)} câu hỏi vào hệ thống!")
                        time.sleep(1) 
                        st.rerun() 
                except Exception as e:
                    st.error(f"Lỗi: {e}")

    # --- GIAO DIỆN CHÍNH LÀM BÀI ---
    if st.session_state.quiz_data:
        # Hiển thị Toast thông báo kết quả câu trước (nếu có)
        if st.session_state.toast_msg:
            st.toast(st.session_state.toast_msg, icon="🔔")
            st.session_state.toast_msg = None

        quiz_len = len(st.session_state.quiz_data)
        idx = st.session_state.current_index
        q_data = st.session_state.quiz_data[idx]
        
        st.progress((idx + 1) / quiz_len, text=f"Câu hỏi {idx + 1}/{quiz_len}")
        st.markdown(f"**Câu {idx + 1}:**")
        st.write(q_data['question'])
        
        correct_ans_str = q_data['correct_answer'].strip()
        is_multiple = len(correct_ans_str) > 1
        user_choice = []
        
        st.write("---")
        
        unique_key = str(hash(q_data['question'])) 

        if is_multiple:
            st.info(f"💡 Chọn {len(correct_ans_str)} đáp án đúng.")
            st.write("Chọn các đáp án:")
            for i, opt in enumerate(q_data['options']):
                chk_key = f"chk_{unique_key}_{i}"
                if st.checkbox(opt, key=chk_key):
                    user_choice.append(opt)
        else:
            choice = st.radio("Chọn đáp án:", q_data['options'], key=f"radio_{unique_key}", index=None)
            if choice:
                user_choice = [choice]

        col_check, col_nav = st.columns([1, 2])
        msg_container = st.container()

        # Nút Kiểm tra thủ công (Vẫn giữ để user check nếu muốn mà chưa next)
        with col_check:
            if st.button("Kiểm tra 🔍"):
                if user_choice:
                    user_chars = sorted([opt.split('.')[0].strip() for opt in user_choice])
                    st.session_state.user_answers[idx] = user_chars
                    calculate_score()
                else:
                    st.warning("Chưa chọn đáp án!")

        # Logic hiển thị kết quả tại chỗ
        if idx in st.session_state.user_answers:
            saved_ans = st.session_state.user_answers[idx]
            correct_chars = sorted(list(correct_ans_str))
            
            if saved_ans == correct_chars:
                msg_container.success("✅ Chính xác!")
            else:
                msg_container.error(f"❌ Sai! Đáp án đúng: {correct_ans_str}")
                if q_data.get('explanation'):
                    msg_container.info(f"Giải thích: {q_data['explanation']}")

        # Nút Điều hướng
        with col_nav:
            c1, c2 = st.columns(2)
            with c1:
                if idx > 0:
                    if st.button("⬅️ Quay lại", use_container_width=True):
                        st.session_state.current_index -= 1
                        st.rerun()
            with c2:
                if idx < quiz_len - 1:
                    if st.button("Tiếp theo ➡️", use_container_width=True):
                        # --- LOGIC MỚI: CHỈ QUA CÂU NẾU ĐÚNG ---
                        if user_choice:
                            # 1. Lưu đáp án
                            user_chars = sorted([opt.split('.')[0].strip() for opt in user_choice])
                            st.session_state.user_answers[idx] = user_chars
                            
                            # 2. Kiểm tra
                            correct_chars = sorted(list(correct_ans_str))
                            
                            if user_chars == correct_chars:
                                # ĐÚNG: Tính điểm và Qua câu
                                st.session_state.toast_msg = f"Câu {idx + 1}: Chính xác! 🎉"
                                calculate_score()
                                st.session_state.current_index += 1
                                st.rerun()
                            else:
                                # SAI: Giữ lại, thông báo lỗi
                                st.session_state.toast_msg = f"Câu {idx + 1}: Sai rồi! Vui lòng chọn lại."
                                st.rerun()
                        else:
                            st.session_state.toast_msg = f"Câu {idx + 1}: Bạn đã bỏ qua (Chưa chọn đáp án)"
                            st.rerun()
                else:
                    if st.button("Hoàn thành 🏁", use_container_width=True):
                        st.balloons()
                        calculate_score()
                        st.success(f"Kết quả: {st.session_state.score}/{quiz_len} câu đúng!")

    elif not st.session_state.full_data:
        st.info("👈 Chưa có dữ liệu. Vui lòng tải file Word (.docx) lần đầu tiên.")

if __name__ == "__main__":
    if st.runtime.exists():
        main()
    else:
        sys.argv = ["streamlit", "run", sys.argv[0]]
        sys.exit(stcli.main())