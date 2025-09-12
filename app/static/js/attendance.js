// Attendance system JavaScript utilities

class AttendanceManager {
  constructor() {
    this.initializeEventListeners();
    this.setupKeyboardShortcuts();
  }

  initializeEventListeners() {
    // Auto-save functionality
    const form = document.querySelector('form[method="POST"]');
    if (form) {
      this.setupAutoSave(form);
    }

    // Search functionality
    this.setupStudentSearch();

    // Bulk actions
    this.setupBulkActions();
  }

  setupAutoSave(form) {
    let timeout;
    const inputs = form.querySelectorAll('input[type="radio"]');

    inputs.forEach((input) => {
      input.addEventListener("change", () => {
        clearTimeout(timeout);
        timeout = setTimeout(() => {
          this.showSaveIndicator();
        }, 1000);
      });
    });
  }

  setupStudentSearch() {
    const searchInput = document.getElementById("student-search");
    if (!searchInput) return;

    searchInput.addEventListener("input", (e) => {
      const query = e.target.value.toLowerCase();
      const studentRows = document.querySelectorAll("[data-student-name]");

      studentRows.forEach((row) => {
        const name = row.dataset.studentName.toLowerCase();
        const visible = name.includes(query);
        row.style.display = visible ? "" : "none";
      });
    });
  }

  setupBulkActions() {
    // Already implemented in templates
  }

  setupKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
      if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
          case "s":
            e.preventDefault();
            this.saveAttendance();
            break;
          case "p":
            e.preventDefault();
            this.markAll("present");
            break;
          case "a":
            e.preventDefault();
            this.markAll("absent");
            break;
        }
      }
    });
  }

  markAll(status) {
    const radios = document.querySelectorAll(
      `input[type="radio"][value="${status}"]`
    );
    radios.forEach((radio) => {
      radio.checked = true;
    });
    this.updateSummary();
  }

  updateSummary() {
    const presentCount = document.querySelectorAll(
      'input[value="present"]:checked'
    ).length;
    const absentCount = document.querySelectorAll(
      'input[value="absent"]:checked'
    ).length;
    const lateCount = document.querySelectorAll(
      'input[value="late"]:checked'
    ).length;

    const summaryElement = document.getElementById("summary");
    if (summaryElement) {
      summaryElement.textContent = `Present: ${presentCount}, Absent: ${absentCount}, Late: ${lateCount}`;
    }
  }

  saveAttendance() {
    const form = document.querySelector('form[method="POST"]');
    if (form) {
      form.submit();
    }
  }

  showSaveIndicator() {
    // Create a temporary save indicator
    const indicator = document.createElement("div");
    indicator.className =
      "fixed top-4 right-4 bg-blue-500 text-white px-4 py-2 rounded-md shadow-lg z-50 fade-in";
    indicator.innerHTML =
      '<i data-lucide="save" class="h-4 w-4 mr-2 inline"></i>Changes detected...';
    document.body.appendChild(indicator);

    setTimeout(() => {
      indicator.remove();
    }, 2000);

    lucide.createIcons();
  }
}

// QR Scanner utilities
class QRScanner {
  constructor() {
    this.scanning = false;
    this.stream = null;
    this.stats = {
      total: 0,
      successful: 0,
      failed: 0,
    };
  }

  async startCamera() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
      });
      return this.stream;
    } catch (error) {
      throw new Error("Camera access denied or not available");
    }
  }

  stopCamera() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
  }

  updateStats(success) {
    this.stats.total++;
    if (success) {
      this.stats.successful++;
    } else {
      this.stats.failed++;
    }
  }

  getStats() {
    return { ...this.stats };
  }
}

// Utility functions
function formatDate(date) {
  return new Intl.DateTimeFormat("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}

function showNotification(message, type = "info") {
  const notification = document.createElement("div");
  notification.className = `fixed top-4 right-4 max-w-sm w-full bg-white border border-gray-200 rounded-lg shadow-lg z-50 fade-in`;

  const iconMap = {
    success: "check-circle",
    error: "x-circle",
    warning: "alert-triangle",
    info: "info",
  };

  const colorMap = {
    success: "text-green-600",
    error: "text-red-600",
    warning: "text-yellow-600",
    info: "text-blue-600",
  };

  notification.innerHTML = `
        <div class="p-4">
            <div class="flex items-start">
                <i data-lucide="${iconMap[type]}" class="h-5 w-5 ${colorMap[type]} mt-0.5 mr-3"></i>
                <div class="flex-1">
                    <p class="text-sm font-medium text-gray-900">${message}</p>
                </div>
                <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                        class="ml-4 text-gray-400 hover:text-gray-600">
                    <i data-lucide="x" class="h-4 w-4"></i>
                </button>
            </div>
        </div>
    `;

  document.body.appendChild(notification);
  lucide.createIcons();

  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentElement) {
      notification.remove();
    }
  }, 5000);
}

// Initialize when DOM is loaded
document.addEventListener("DOMContentLoaded", function () {
  // Initialize attendance manager if on attendance pages
  if (
    document.querySelector(".attendance-page") ||
    window.location.pathname.includes("/attendance/")
  ) {
    new AttendanceManager();
  }

  // Initialize Lucide icons
  lucide.createIcons();
});
