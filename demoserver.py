import socket
import threading

# --- Cấu hình Server ---
HOST = '0.0.0.0'
PORT = 56666

clients = []
nicknames = []
lock = threading.Lock()


# --- GỬI DANH SÁCH NGƯỜI DÙNG ---
def send_user_list():
    """Gửi danh sách người dùng online cho tất cả client."""
    with lock:
        user_string = ",".join(nicknames)
        targets = list(clients)  # làm bản sao để gửi ngoài lock nếu cần
    # Gửi ngoài phần sửa đổi danh sách
    to_remove = []
    for client in targets:
        try:
            client.send(f"#USERS:{user_string}".encode('utf-8'))
        except Exception:
            to_remove.append(client)
    for c in to_remove:
        remove_client(c)


# --- PHÁT TIN NHẮN ---
def broadcast(message, sender_client=None):
    """Gửi tin nhắn đến tất cả client (trừ người gửi nếu cần)."""
    with lock:
        targets = [c for c in clients if c != sender_client]
    to_remove = []
    for client in targets:
        try:
            client.send(message.encode('utf-8'))
        except Exception:
            to_remove.append(client)
    for c in to_remove:
        remove_client(c)


# --- GỬI TIN NHẮN RIÊNG ---
def send_private_message(sender, recipient_name, message):
    """Gửi tin nhắn riêng đến một người cụ thể."""
    recipient_client = None
    with lock:
        if recipient_name in nicknames:
            index = nicknames.index(recipient_name)
            recipient_client = clients[index]
        else:
            # gửi phản hồi lỗi cho sender (nếu sender vẫn tồn tại)
            if sender in nicknames:
                sidx = nicknames.index(sender)
                try:
                    clients[sidx].send(f"SERVER: Người dùng '{recipient_name}' không tồn tại.".encode('utf-8'))
                except Exception:
                    # nếu gửi tới sender lỗi -> xóa sender
                    remove_client(clients[sidx])
            return

    # gửi riêng ngoài lock để tránh deadlock
    try:
        recipient_client.send(f"#PRIVATE:{sender}:{message}".encode('utf-8'))
        print(f"[PM] {sender} → {recipient_name}: {message}")
    except Exception:
        remove_client(recipient_client)


# --- XÓA CLIENT ---
def remove_client(client):
    """Xóa client khỏi danh sách và thông báo."""
    nickname = None
    # chỉ thao tác trên cấu trúc dữ liệu bên trong lock, không gọi broadcast/send_user_list trong lock
    with lock:
        if client in clients:
            index = clients.index(client)
            nickname = nicknames[index]
            clients.pop(index)
            nicknames.pop(index)
    try:
        client.close()
    except:
        pass

    if nickname:
        print(f"[{nickname}] đã ngắt kết nối.")
        # Thông báo và cập nhật danh sách (thực hiện ngoài lock)
        broadcast(f"SERVER: {nickname} đã rời khỏi phòng chat!")
        send_user_list()


# --- XỬ LÝ MỖI CLIENT ---
def handle_client(client):
    nickname = None
    try:
        # 1. Nhận tên
        client.send("NICK".encode('utf-8'))
        data = client.recv(1024)
        if not data:
            # không có data -> kết nối đóng ngay
            client.close()
            return
        nickname = data.decode('utf-8').strip()

        with lock:
            nicknames.append(nickname)
            clients.append(client)

        print(f"[{nickname}] đã kết nối.")
        broadcast(f"SERVER: {nickname} đã tham gia phòng chat!")
        send_user_list()

        # 2. Nhận tin nhắn
        while True:
            data = client.recv(1024)
            if not data:
                break
            message = data.decode('utf-8')

            if message == "!DISCONNECT":
                break

            # Kiểm tra tin nhắn riêng
            if message.startswith("@"):
                try:
                    recipient_name, private_msg = message[1:].split(" ", 1)
                    send_private_message(nickname, recipient_name, private_msg)
                except ValueError:
                    try:
                        client.send("SERVER: Cú pháp tin nhắn riêng không hợp lệ. Dùng: @tên nội_dung".encode('utf-8'))
                    except Exception:
                        remove_client(client)
            else:
                broadcast(f"{nickname}: {message}", sender_client=client)

    except ConnectionResetError:
        print(f"Lỗi: {nickname if nickname else 'Một client'} bị ngắt kết nối đột ngột.")
    except Exception as e:
        print(f"Lỗi từ {nickname if nickname else 'Một client'}: {e}")
    finally:
        remove_client(client)


# --- CHẠY SERVER ---
def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen()
    print(f"✅ Server đang lắng nghe trên {HOST}:{PORT}...")

    while True:
        client, address = server.accept()
        print(f"🔗 Kết nối từ {address}")
        thread = threading.Thread(target=handle_client, args=(client,))
        thread.daemon = True
        thread.start()


if __name__ == "__main__":
    start_server()
