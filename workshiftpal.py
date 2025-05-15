import time
import threading
import tkinter as tk
import customtkinter as ctk
import win32gui
from win10toast import ToastNotifier

# === Distraction Monitor ===

DISTRACTION_KEYWORDS = ['youtube', 'facebook', 'instagram', 'tiktok', 'twitter', 'reddit']

class WorkspaceMonitor:
    def __init__(self):
        self.distraction_time = 0
        self.last_check = time.time()

    def get_active_window_title(self):
        try:
            window = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(window).lower()
        except:
            return ""

    def is_distracted(self):
        title = self.get_active_window_title()
        return any(keyword in title for keyword in DISTRACTION_KEYWORDS)

    def update_distraction_time(self):
        now = time.time()
        elapsed = now - self.last_check
        self.last_check = now

        if self.is_distracted():
            self.distraction_time += elapsed
        else:
            self.distraction_time = max(0, self.distraction_time - elapsed * 0.5)

        return self.distraction_time

# === Notifier ===

class Notifier:
    def __init__(self):
        self.toaster = ToastNotifier()

    def notify(self, title, message, duration=5):
        try:
            self.toaster.show_toast(title, message, duration=duration, threaded=True)
        except Exception as e:
            print(f"Notification failed: {e}")

# === Tracker ===

class WorkTracker:
    def __init__(self):
        self.slack_count = 0
        self.continuous_work_time = 0  # in minutes
        self.last_penalty = 15

    def add_slack(self):
        self.slack_count += 1
        penalty = 15 + (self.slack_count * 2) - (self.continuous_work_time // 30)
        penalty = max(penalty, 15)
        self.last_penalty = penalty
        self.continuous_work_time = 0
        return penalty

    def add_work_time(self, minutes):
        self.continuous_work_time += minutes

    def reset_rewards(self):
        self.continuous_work_time = 0

    def reset_slack(self):
        self.slack_count = 0

# === Main GUI ===

class WorkShiftApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WorkShiftPal")
        self.geometry("400x300")
        ctk.set_appearance_mode("dark")

        self.timer_label = ctk.CTkLabel(self, text="Shift Time: 60:00", font=ctk.CTkFont(size=24))
        self.timer_label.pack(pady=20)

        self.slack_button = ctk.CTkButton(self, text="I Slacked Off", command=self.handle_slack)
        self.slack_button.pack(pady=10)

        self.status_label = ctk.CTkLabel(self, text="Status: Focused")
        self.status_label.pack(pady=10)

        self.running = True
        self.shift_time = 60 * 60
        self.remaining = self.shift_time

        self.tracker = WorkTracker()
        self.notifier = Notifier()
        self.monitor = WorkspaceMonitor()

        self.start_timer_thread()
        self.start_monitor_thread()

    def update_timer_label(self):
        mins = int(self.remaining) // 60
        secs = int(self.remaining) % 60
        self.timer_label.configure(text=f"Shift Time: {mins:02}:{secs:02}")

    def handle_slack(self):
        added = self.tracker.add_slack()
        self.remaining += added * 60
        self.status_label.configure(text=f"Slacked off! Added {added} mins.")

    def ask_continue(self):
        self.notifier.notify("Shift Complete", "Want to work another hour?")
        response = tk.messagebox.askyesno("Shift Complete", "Continue working another hour?")
        if response:
            self.tracker.add_work_time(60)
            self.remaining = self.shift_time
        else:
            self.running = False
            self.destroy()

    def start_timer_thread(self):
        def timer_loop():
            while self.running:
                if self.remaining > 0:
                    self.remaining -= 1
                    self.update_timer_label()
                    time.sleep(1)
                else:
                    self.ask_continue()
        threading.Thread(target=timer_loop, daemon=True).start()

    def start_monitor_thread(self):
        def monitor_loop():
            while self.running:
                distraction_time = self.monitor.update_distraction_time()
                if distraction_time > 30:
                    self.notifier.notify("Distraction Alert", "Are you still working?")
                    self.status_label.configure(text="Status: Detected Distraction!")
                time.sleep(10)
        threading.Thread(target=monitor_loop, daemon=True).start()

if __name__ == "__main__":
    app = WorkShiftApp()
    app.mainloop()
