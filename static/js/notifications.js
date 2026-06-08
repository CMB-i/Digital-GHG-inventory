document.addEventListener("DOMContentLoaded", () => {
    const bellBtn = document.getElementById("btn-bell");
    const bellDropdown = document.getElementById("bell-dropdown");
    const bellBadge = document.getElementById("bell-badge");
    const bellList = document.getElementById("bell-list");
    const markAllBtn = document.getElementById("btn-bell-mark-all-read");
    const bellContainer = document.getElementById("notification-bell-container");

    if (!bellBtn) return;

    // Helper to format date relative to now or compact format
    function formatTime(isoString) {
        const date = new Date(isoString);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHrs = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHrs / 24);

        if (diffMins < 1) return "Just now";
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHrs < 24) return `${diffHrs}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;

        return date.toLocaleDateString("en-IN", { day: 'numeric', month: 'short' });
    }

    // Update unread count badge
    async function updateNotificationBell() {
        try {
            const res = await fetch("/module/NOTIFY/unread-count");
            const result = await res.json();
            if (result.status === "success") {
                const count = result.data.unread_count;
                if (count > 0) {
                    bellBadge.textContent = count;
                    bellBadge.classList.remove("hidden");
                } else {
                    bellBadge.classList.add("hidden");
                    bellBadge.textContent = "0";
                }
            }
        } catch (err) {
            console.error("Error updating notification bell count:", err);
        }
    }

    // Expose globally so other pages can update the bell count
    window.updateNotificationBell = updateNotificationBell;

    // Fetch and render recent notifications in dropdown
    async function loadDropdownNotifications() {
        try {
            bellList.innerHTML = `
                <div class="p-4 text-center text-xs text-slate-400">
                    <svg class="animate-spin h-5 w-5 mx-auto mb-2 text-indigo-600" fill="none" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Loading notifications...
                </div>
            `;

            const res = await fetch("/module/NOTIFY/recent");
            const result = await res.json();
            if (result.status === "success") {
                const notifications = result.data;
                if (notifications.length === 0) {
                    bellList.innerHTML = `
                        <div class="p-5 text-center text-xs text-slate-400">
                            No notifications yet.
                        </div>
                    `;
                    return;
                }

                bellList.innerHTML = "";
                notifications.forEach(n => {
                    const row = document.createElement("div");
                    row.className = `p-3 flex items-start space-x-2.5 hover:bg-slate-50 transition-colors text-xs cursor-pointer ${!n.is_read ? 'bg-indigo-50/20' : ''}`;
                    row.dataset.id = n.id;
                    row.dataset.url = n.link_url;

                    row.innerHTML = `
                        <span class="mt-1.5 h-1.5 w-1.5 rounded-full ${!n.is_read ? 'bg-indigo-600' : 'bg-transparent'} flex-shrink-0"></span>
                        <div class="flex-1 space-y-0.5 min-w-0">
                            <p class="text-slate-700 leading-normal ${!n.is_read ? 'font-medium' : ''}">${n.message}</p>
                            <p class="text-[10px] text-slate-400">${formatTime(n.created_at)}</p>
                        </div>
                    `;

                    row.addEventListener("click", async () => {
                        try {
                            // Mark read via API
                            if (!n.is_read) {
                                await fetch(`/module/NOTIFY/${n.id}/read`, {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" }
                                });
                            }
                        } catch (err) {
                            console.error("Error marking read:", err);
                        }

                        // Redirect to the notification target page
                        if (n.link_url && n.link_url !== "#") {
                            window.location.href = n.link_url;
                        }
                    });

                    bellList.appendChild(row);
                });
            }
        } catch (err) {
            console.error("Error loading dropdown notifications:", err);
            bellList.innerHTML = `
                <div class="p-4 text-center text-xs text-rose-500">
                    Failed to load notifications.
                </div>
            `;
        }
    }

    // Toggle dropdown visibility
    bellBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        const isHidden = bellDropdown.classList.contains("hidden");
        if (isHidden) {
            bellDropdown.classList.remove("hidden");
            loadDropdownNotifications();
        } else {
            bellDropdown.classList.add("hidden");
        }
    });

    // Close dropdown on click outside
    document.addEventListener("click", (e) => {
        if (bellContainer && !bellContainer.contains(e.target)) {
            bellDropdown.classList.add("hidden");
        }
    });

    // Handle "Mark all read" from bell dropdown
    markAllBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        try {
            const res = await fetch("/module/NOTIFY/mark-all-read", {
                method: "POST",
                headers: { "Content-Type": "application/json" }
            });
            const result = await res.json();
            if (result.status === "success") {
                updateNotificationBell();
                loadDropdownNotifications();
                // If we are currently on the notifications page, reload it too
                if (window.location.pathname === "/module/NOTIFY/") {
                    window.location.reload();
                }
            }
        } catch (err) {
            console.error("Error marking all read from dropdown:", err);
        }
    });

    // Initialize and start polling
    updateNotificationBell();
    setInterval(updateNotificationBell, 30000); // Poll every 30 seconds
});
