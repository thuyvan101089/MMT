import customtkinter as ctk
import socket
import threading
from tkinter import simpledialog, messagebox

# --- Cấu hình Mạng ---
HOST = 'localhost'#IP của Server (lưu ý: thường là '127.0.0.1' nếu server chạy local)
PORT = 56666     # Port của Server
client_socket = None
nickname = None

# --- Khởi tạo GUI ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
app = ctk.CTk()
app.title("Ứng Dụng Chat Đa Người Dùng")
app.geometry("500x500")
app.minsize(420, 320)

# --- Khung Hiển Thị Người Dùng ---
users_frame = ctk.CTkFrame(app, width=140)
users_frame.pack(side="right", fill="y", padx=5, pady=5)
users_label = ctk.CTkLabel(users_frame, text="Người Dùng Trực Tuyến:")
users_label.pack(pady=5)
user_list = ctk.CTkTextbox(users_frame, width=140, height=350, state="disabled")
user_list.pack(padx=5, pady=5, fill="y", expand=True)

# --- Khung Chat ---
chat_box = ctk.CTkTextbox(app, width=320, height=350, state="disabled")
chat_box.pack(pady=10, side="top", fill="both", expand=True, padx=10) # Điều chỉnh layout để nằm trên và mở rộng

# --- Khung Nhập Liệu: đặt entry và nút Gửi vào một frame để không bị chen chúc ---
input_frame = ctk.CTkFrame(app)
input_frame.pack(side="bottom", fill="x", padx=10, pady=5)

entry = ctk.CTkEntry(input_frame, placeholder_text="Nhập tin nhắn (Riêng tư: @tên ...)")
entry.pack(side="left", fill="x", expand=True, padx=(0,8))

send_btn = ctk.CTkButton(input_frame, text="Gửi", command=lambda e=None: send_message())
send_btn.pack(side="right")

# --- Các Hàm Xử Lý GUI và Mạng ---

def update_user_list(users):
    """Cập nhật danh sách người dùng vào khung user_list.
    Tham số users có thể là list[str] hoặc string (dấu phẩy phân tách)."""
    # Chuẩn hoá input về list
    if isinstance(users, str):
        users_string = users.strip()
        if users_string == "":
            users_list = []
        else:
            users_list = [u.strip() for u in users_string.split(',') if u.strip()]
    elif isinstance(users, list):
        users_list = [u.strip() for u in users if u and u.strip()]
    else:
        users_list = []

    user_list.configure(state="normal")
    user_list.delete('1.0', 'end') # Xóa nội dung cũ

    for user in users_list:
        user_list.insert('end', f"{user}\n")

    user_list.configure(state="disabled")

def clear_user_list():
    """Xoá danh sách người dùng (ví dụ khi mất kết nối)."""
    update_user_list([])

def update_chat_box(message):
    """Cập nhật nội dung vào khung chat (an toàn cho GUI)."""
    chat_box.configure(state="normal")
    chat_box.insert("end", f"{message}\n")
    chat_box.see("end") # Cuộn xuống cuối
    chat_box.configure(state="disabled")

def send_message(event=None):
    """Lấy tin nhắn từ entry và gửi đến Server.
    NOTE: thêm 'local echo' để hiển thị tin nhắn của chính người dùng ngay khi gửi,
    phòng trường hợp server không broadcast lại cho sender."""
    global client_socket, nickname
    msg = entry.get().strip()
    entry.delete(0, 'end')

    if not msg or client_socket is None:
        return

    try:
        client_socket.send(msg.encode('utf-8'))

        # Hiển thị local echo khi gửi thành công
        sender = nickname if nickname else "Bạn"
        if msg.startswith("@"):
            # Phân tích dạng "@recipient nội dung..."
            parts = msg.split(' ', 1)
            recipient_token = parts[0]
            content = parts[1] if len(parts) > 1 else ""
            recipient = recipient_token[1:] if len(recipient_token) > 1 else ""
            # Hiển thị rõ là tin nhắn riêng
            if content:
                update_chat_box(f"(Bạn ➜ {recipient}) {sender}: {content}")
            else:
                # Nếu chỉ nhập "@tên" mà không có nội dung, hiện nguyên msg
                update_chat_box(f"(Bạn ➜ {recipient}) {sender}: {recipient_token}")
        else:
            update_chat_box(f"{sender}: {msg}")

    except Exception:
        update_chat_box("LỖI KẾT NỐI: Không thể gửi tin nhắn.")
        if client_socket:
            try:
                client_socket.close()
            except:
                pass
        app.quit()

def receive_messages():
    """Chạy trong luồng riêng, liên tục lắng nghe tin nhắn từ Server."""
    global client_socket, nickname
    while True:
        try:
            data = client_socket.recv(1024)
            if not data:
                # Server đã đóng kết nối
                update_chat_box("--- MẤT KẾT NỐI VỚI MÁY CHỦ (server đóng kết nối) ---")
                clear_user_list()
                if client_socket:
                    try:
                        client_socket.close()
                    except:
                        pass
                break

            message = data.decode('utf-8')

            if message == 'NICK':
                # Server yêu cầu gửi nickname
                client_socket.send(nickname.encode('utf-8'))

            # XỬ LÝ TIN NHẮN DANH SÁCH NGƯỜI DÙNG (#USERS)
            elif message.startswith("#USERS:"):
                users_string = message[len("#USERS:"):].strip()
                update_user_list(users_string)

            # Tùy chọn: server có thể gửi thông báo join/left
            elif message.startswith("#JOIN:"):
                joined = message[len("#JOIN:"):].strip()
                update_chat_box(f"--- {joined} đã tham gia ---")
                # server tốt hơn là broadcast #USERS sau khi một client join
            elif message.startswith("#LEFT:"):
                left = message[len("#LEFT:"):].strip()
                update_chat_box(f"--- {left} đã rời ---")
                # server nên broadcast #USERS sau khi một client rời
            else:
                update_chat_box(message)

        except ConnectionAbortedError:
            break
        except Exception:
            update_chat_box("--- ĐÃ MẤT KẾT NỐI VỚI MÁY CHỦ (lỗi) ---")
            clear_user_list()
            if client_socket:
                try:
                    client_socket.close()
                except:
                    pass
            break

def connect_to_server():
    """Xử lý việc kết nối đến Server và nhập nickname."""
    global client_socket, nickname

    # 1. Nhập Nickname
    nickname = simpledialog.askstring("Tên Người Dùng", "Vui lòng nhập tên của bạn:", parent=app)
    if not nickname or nickname.strip() == "":
        app.quit()
        return

    # 2. Tạo và Kết nối Socket
    try:
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect((HOST, PORT))
    except Exception:
        messagebox.showerror("LỖI KẾT NỐI", f"Không thể kết nối đến Máy Chủ tại {HOST}:{PORT}. Vui lòng kiểm tra Server đã chạy chưa.")
        app.quit()
        return

    # 3. Khởi động luồng nhận tin nhắn
    receive_thread = threading.Thread(target=receive_messages)
    receive_thread.daemon = True
    receive_thread.start()

# Cho phép nhấn Enter để gửi tin nhắn
entry.bind("<Return>", send_message)

# Kết nối Server ngay khi ứng dụng khởi động
app.after(100, connect_to_server)

# Hàm đóng socket khi ứng dụng đóng
def on_closing():
    if client_socket:
        try:
            # Tùy chọn: gửi thông điệp rời nếu server hỗ trợ, ví dụ "QUIT"
            # client_socket.send("QUIT".encode('utf-8'))
            client_socket.close()
        except:
            pass # Socket đã đóng rồi
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_closing)
app.mainloop()
