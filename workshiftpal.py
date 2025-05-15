import time
import threading
import tkinter as tk
import customtkinter as ctk
import win32gui
from win10toast import ToastNotifier
from tkinter import messagebox

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
        self.continuous_work_time = 0
        self.last_penalty = 15
        self.notif_cooldown = 60  # seconds between notifications
        self.last_notif_time = 0
        self.notif_frequency_multiplier = 1.0  # will increase or decrease

    def add_slack(self):
        self.slack_count += 1
        penalty = 15 + (self.slack_count * 2) - (self.continuous_work_time // 30)
        penalty = max(penalty, 15)
        self.last_penalty = penalty
        self.continuous_work_time = 0
        # Decrease notification frequency if user says "No" to continue
        self.notif_frequency_multiplier = min(self.notif_frequency_multiplier + 0.5, 5.0)
        return penalty

    def add_work_time(self, minutes):
        self.continuous_work_time += minutes
        # If user says "Yes" to continue, reduce notification frequency (fewer nagging notifs)
        self.notif_frequency_multiplier = max(self.notif_frequency_multiplier * 0.5, 0.1)

    def reset_rewards(self):
        self.continuous_work_time = 0

    def reset_slack(self):
        self.slack_count = 0

    def can_notify(self):
        return (time.time() - self.last_notif_time) > (self.notif_cooldown * self.notif_frequency_multiplier)

    def update_last_notif_time(self):
        self.last_notif_time = time.time()

# === Main App ===
class WorkShiftApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WorkShiftPal")
        self.geometry("400x300")
        ctk.set_appearance_mode("dark")

        self.timer_label = ctk.CTkLabel(self, text="Shift Time: 60:00", font=ctk.CTkFont(size=24))
        self.timer_label.pack(pady=20)

        self.start_button = ctk.CTkButton(self, text="Start Shift", command=self.start_shift)
        self.start_button.pack(pady=10)

        # Container frame for slack button and yes/no question and buttons, so they stay in the same place
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(pady=10)

        self.slack_button = ctk.CTkButton(self.button_frame, text="I Slacked Off", command=self.handle_slack, state="disabled")
        self.slack_button.pack()

        # Label for distraction question (hidden initially)
        self.question_label = ctk.CTkLabel(self.button_frame, text="Are you still working?", font=ctk.CTkFont(size=14))
        # Yes/No buttons (hidden initially)
        self.yes_button = ctk.CTkButton(self.button_frame, text="Yes", width=80, command=lambda: self.respond_to_distraction(True))
        self.no_button = ctk.CTkButton(self.button_frame, text="No", width=80, command=lambda: self.respond_to_distraction(False))

        self.status_label = ctk.CTkLabel(self, text="Status: Not Started")
        self.status_label.pack(pady=10)

        self.running = False
        self.shift_time = 60 * 60
        self.remaining = self.shift_time
        self.timer_started = False

        self.tracker = WorkTracker()
        self.notifier = Notifier()
        self.monitor = WorkspaceMonitor()

        self.distraction_alert_active = False

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
        response = messagebox.askyesno("Shift Complete", "Continue working another hour?")
        if response:
            self.tracker.add_work_time(60)
            self.remaining = self.shift_time
        else:
            self.running = False
            self.destroy()

    def start_shift(self):
        if not self.timer_started:
            self.running = True
            self.start_button.configure(state="disabled")
            self.slack_button.configure(state="normal")
            self.status_label.configure(text="Status: Working")
            self.timer_started = True
            self.start_timer_thread()
            self.start_monitor_thread()

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
                if distraction_time > 30 and not self.distraction_alert_active and self.tracker.can_notify():
                    self.distraction_alert_active = True
                    self.tracker.update_last_notif_time()
                    self.notifier.notify("Distraction Alert", "Are you still working?")
                    self.show_yes_no_buttons()
                time.sleep(10)
        threading.Thread(target=monitor_loop, daemon=True).start()

    def show_yes_no_buttons(self):
        # Hide slack button
        self.slack_button.pack_forget()
        # Show question label and buttons side by side
        self.question_label.pack(pady=(0,5))
        self.yes_button.pack(side="left", padx=10)
        self.no_button.pack(side="left", padx=10)

    def hide_yes_no_buttons(self):
        self.question_label.pack_forget()
        self.yes_button.pack_forget()
        self.no_button.pack_forget()
        self.slack_button.pack()

    def respond_to_distraction(self, is_working):
        if is_working:
            self.status_label.configure(text="Status: Thanks for confirming you're working!")
            self.tracker.add_work_time(10)  # reward: reduce notif frequency a bit
        else:
            self.status_label.configure(text="Status: Acknowledged distraction, adding slack penalty.")
            added = self.tracker.add_slack()
            self.remaining += added * 60
        self.distraction_alert_active = False
        self.hide_yes_no_buttons()

if __name__ == "__main__":
    app = WorkShiftApp()
    app.mainloop()
