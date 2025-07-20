// AIAutoBangumi2 Common JavaScript Functions

// Axios默认配置
axios.defaults.timeout = 30000;
axios.defaults.headers.common['X-Requested-With'] = 'XMLHttpRequest';

// 添加请求拦截器
axios.interceptors.request.use(
    config => {
        // 可以在这里添加loading状态
        return config;
    },
    error => {
        return Promise.reject(error);
    }
);

// 添加响应拦截器
axios.interceptors.response.use(
    response => {
        return response;
    },
    error => {
        if (error.response?.status === 401) {
            // 未授权，重定向到登录页面
            window.location.href = '/login.html';
        }
        return Promise.reject(error);
    }
);

// 通用工具函数
const Utils = {
    // 格式化日期
    formatDate(dateString) {
        if (!dateString) return '从未';
        const date = new Date(dateString);
        return date.toLocaleString('zh-CN');
    },
    
    // 格式化文件大小
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    // 格式化时间间隔
    formatInterval(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        
        if (hours > 0) {
            return `${hours}小时${minutes > 0 ? minutes + '分钟' : ''}`;
        } else if (minutes > 0) {
            return `${minutes}分钟`;
        } else {
            return `${seconds}秒`;
        }
    },
    
    // 状态文本映射
    getStatusText(status) {
        const statusMap = {
            'downloading': '下载中',
            'downloaded': '已完成',
            'failed': '失败',
            'pending': '待处理',
            'completed': '已完成'
        };
        return statusMap[status] || status;
    },
    
    // 文件类型文本映射
    getFileTypeText(fileType) {
        const typeMap = {
            'episode': '剧集',
            'subtitle': '字幕',
            'op': 'OP',
            'ed': 'ED',
            'sp': '特别篇',
            'other': '其他'
        };
        return typeMap[fileType] || '其他';
    },
    
    // 从URL获取参数
    getUrlParam(name) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(name);
    },
    
    // 防抖函数
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },
    
    // 节流函数
    throttle(func, limit) {
        let lastFunc;
        let lastRan;
        return function() {
            const context = this;
            const args = arguments;
            if (!lastRan) {
                func.apply(context, args);
                lastRan = Date.now();
            } else {
                clearTimeout(lastFunc);
                lastFunc = setTimeout(function() {
                    if ((Date.now() - lastRan) >= limit) {
                        func.apply(context, args);
                        lastRan = Date.now();
                    }
                }, limit - (Date.now() - lastRan));
            }
        }
    },
    
    // 确认对话框
    confirm(message, title = '确认') {
        return new Promise((resolve) => {
            const result = window.confirm(`${title}\n\n${message}`);
            resolve(result);
        });
    },
    
    // Toast通知 (简单实现)
    toast(message, type = 'info', duration = 3000) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 4px;
            color: white;
            z-index: 10000;
            transition: all 0.3s ease;
        `;
        
        // 设置颜色
        const colors = {
            'info': '#667eea',
            'success': '#38a169',
            'error': '#e53e3e',
            'warning': '#dd6b20'
        };
        toast.style.backgroundColor = colors[type] || colors.info;
        
        document.body.appendChild(toast);
        
        // 动画显示
        setTimeout(() => {
            toast.style.transform = 'translateX(0)';
            toast.style.opacity = '1';
        }, 10);
        
        // 自动移除
        setTimeout(() => {
            toast.style.transform = 'translateX(100%)';
            toast.style.opacity = '0';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);
    }
};

// 使工具函数全局可用
window.Utils = Utils;

// Vue全局混入
if (typeof Vue !== 'undefined' && Vue.createApp) {
    // Vue 3 全局属性
    const globalProperties = {
        $utils: Utils,
        $formatDate: Utils.formatDate,
        $formatFileSize: Utils.formatFileSize,
        $formatInterval: Utils.formatInterval,
        $getStatusText: Utils.getStatusText,
        $getFileTypeText: Utils.getFileTypeText,
        $toast: Utils.toast
    };
    
    // 可以在每个Vue应用实例中使用
    window.addGlobalProperties = function(app) {
        Object.keys(globalProperties).forEach(key => {
            app.config.globalProperties[key] = globalProperties[key];
        });
    };
}

// 页面加载完成后执行
document.addEventListener('DOMContentLoaded', function() {
    // 添加全局键盘快捷键
    document.addEventListener('keydown', function(e) {
        // Ctrl+/ 显示快捷键帮助（如果需要的话）
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            // 可以显示快捷键帮助
        }
        
        // ESC 关闭模态框或返回
        if (e.key === 'Escape') {
            // 可以添加关闭模态框的逻辑
        }
    });
});

console.log('AIAutoBangumi2 common scripts loaded');
