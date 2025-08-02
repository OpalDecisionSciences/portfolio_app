/**
 * Restaurant Cart System
 * Handles cart functionality with Django backend integration
 */

class RestaurantCart {
    constructor(restaurantId) {
        this.restaurantId = restaurantId;
        this.cart = this.loadCart();
        this.apiEndpoints = {
            get: `/restaurants/api/cart/`,
            add: `/restaurants/api/cart/add/`,
            remove: `/restaurants/api/cart/remove/`,
            update: `/restaurants/api/cart/update/`,
            clear: `/restaurants/api/cart/clear/`,
            llmInteraction: `/restaurants/api/cart/llm-interaction/`
        };
        this.initializeCart();
    }

    // Load cart from localStorage and sync with server
    loadCart() {
        const savedCart = localStorage.getItem(`cart_${this.restaurantId}`);
        return savedCart ? JSON.parse(savedCart) : [];
    }

    // Save cart to localStorage
    saveCart() {
        localStorage.setItem(`cart_${this.restaurantId}`, JSON.stringify(this.cart));
    }

    // Get CSRF token for Django requests
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || 
               document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || 
               '';
    }

    // Initialize cart UI and sync with server
    async initializeCart() {
        try {
            await this.syncWithServer();
            this.updateCartUI();
            this.bindEvents();
        } catch (error) {
            console.warn('Failed to sync with server, using local cart:', error);
            this.updateCartUI();
            this.bindEvents();
        }
    }

    // Sync local cart with server
    async syncWithServer() {
        try {
            const response = await fetch(this.apiEndpoints.get, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin'
            });

            if (!response.ok) throw new Error('Failed to fetch cart');

            const serverCart = await response.json();
            
            // Merge server cart with local cart (server takes precedence)
            if (serverCart.items && serverCart.items.length > 0) {
                this.cart = serverCart.items.map(item => ({
                    id: item.menu_item_id,
                    name: item.menu_item_name,
                    price: parseFloat(item.price),
                    quantity: item.quantity,
                    notes: item.notes || ''
                }));
                this.saveCart();
            }

        } catch (error) {
            console.warn('Cart sync failed:', error);
        }
    }

    // Add item to cart
    async addItem(itemId, itemName, itemPrice, quantity = 1, notes = '') {
        try {
            // Update local cart first for immediate UI feedback
            const existingItemIndex = this.cart.findIndex(item => item.id === itemId);
            
            if (existingItemIndex !== -1) {
                this.cart[existingItemIndex].quantity += quantity;
            } else {
                this.cart.push({
                    id: itemId,
                    name: itemName,
                    price: parseFloat(itemPrice),
                    quantity: quantity,
                    notes: notes
                });
            }

            this.saveCart();
            this.updateCartUI();

            // Sync with server
            const response = await fetch(this.apiEndpoints.add, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    menu_item_id: itemId,
                    quantity: quantity,
                    notes: notes
                })
            });

            if (!response.ok) {
                throw new Error('Failed to add item to server cart');
            }

            const result = await response.json();
            this.showCartMessage(`✅ Added ${quantity}x ${itemName} to cart!`, 'success');

            return result;

        } catch (error) {
            console.error('Error adding item to cart:', error);
            this.showCartMessage(`❌ Failed to add ${itemName} to cart`, 'error');
            
            // Rollback local cart on server error
            this.revertCartChange();
        }
    }

    // Remove item from cart
    async removeItem(itemId) {
        try {
            const itemIndex = this.cart.findIndex(item => item.id === itemId);
            if (itemIndex === -1) return;

            const removedItem = this.cart[itemIndex];
            this.cart.splice(itemIndex, 1);
            this.saveCart();
            this.updateCartUI();

            // Sync with server
            const response = await fetch(this.apiEndpoints.remove, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    menu_item_id: itemId
                })
            });

            if (!response.ok) {
                throw new Error('Failed to remove item from server cart');
            }

            this.showCartMessage(`🗑️ Removed ${removedItem.name} from cart`, 'info');

        } catch (error) {
            console.error('Error removing item from cart:', error);
            this.showCartMessage(`❌ Failed to remove item from cart`, 'error');
        }
    }

    // Update item quantity
    async updateQuantity(itemId, newQuantity) {
        try {
            const itemIndex = this.cart.findIndex(item => item.id === itemId);
            if (itemIndex === -1) return;

            if (newQuantity <= 0) {
                await this.removeItem(itemId);
                return;
            }

            const oldQuantity = this.cart[itemIndex].quantity;
            this.cart[itemIndex].quantity = newQuantity;
            this.saveCart();
            this.updateCartUI();

            // Sync with server
            const response = await fetch(this.apiEndpoints.update, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    menu_item_id: itemId,
                    quantity: newQuantity
                })
            });

            if (!response.ok) {
                throw new Error('Failed to update item quantity on server');
            }

        } catch (error) {
            console.error('Error updating item quantity:', error);
            this.showCartMessage(`❌ Failed to update quantity`, 'error');
        }
    }

    // Clear entire cart
    async clearCart() {
        try {
            this.cart = [];
            this.saveCart();
            this.updateCartUI();

            // Sync with server
            const response = await fetch(this.apiEndpoints.clear, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin'
            });

            if (!response.ok) {
                throw new Error('Failed to clear cart on server');
            }

            this.showCartMessage(`🗑️ Cart cleared!`, 'info');

        } catch (error) {
            console.error('Error clearing cart:', error);
            this.showCartMessage(`❌ Failed to clear cart`, 'error');
        }
    }

    // Update cart UI
    updateCartUI() {
        const cartItems = document.getElementById('cartItems');
        const cartCount = document.getElementById('cartCount');
        const cartTotal = document.getElementById('cartTotal');
        const cartTotalAmount = document.getElementById('cartTotalAmount');

        if (!cartItems || !cartCount) return;

        // Update cart count
        const totalItems = this.cart.reduce((sum, item) => sum + item.quantity, 0);
        cartCount.textContent = totalItems;

        // Update cart badge visibility
        const cartBadge = document.querySelector('.cart-count');
        if (cartBadge) {
            cartBadge.style.display = totalItems > 0 ? 'inline-block' : 'none';
        }

        if (this.cart.length === 0) {
            cartItems.innerHTML = '<p style="text-align: center; color: #7f8c8d; margin: 20px 0;">Your cart is empty</p>';
            if (cartTotal) cartTotal.style.display = 'none';
            return;
        }

        // Build cart items HTML
        let cartHTML = '';
        let total = 0;

        this.cart.forEach(item => {
            const subtotal = item.price * item.quantity;
            total += subtotal;

            cartHTML += `
                <div class="cart-item" data-item-id="${item.id}">
                    <div class="cart-item-info">
                        <div class="cart-item-name">${item.name}</div>
                        <div class="cart-item-controls">
                            <button class="quantity-btn" onclick="cartSystem.updateQuantity('${item.id}', ${item.quantity - 1})">-</button>
                            <span class="quantity">${item.quantity}</span>
                            <button class="quantity-btn" onclick="cartSystem.updateQuantity('${item.id}', ${item.quantity + 1})">+</button>
                        </div>
                        <div class="cart-item-price">$${subtotal.toFixed(2)}</div>
                        <button class="remove-item-btn" onclick="cartSystem.removeItem('${item.id}')" title="Remove item">
                            <i class="icon-close"></i>
                        </button>
                    </div>
                    ${item.notes ? `<div class="cart-item-notes">${item.notes}</div>` : ''}
                </div>
            `;
        });

        cartItems.innerHTML = cartHTML;
        
        if (cartTotalAmount) {
            cartTotalAmount.textContent = `$${total.toFixed(2)}`;
        }
        if (cartTotal) {
            cartTotal.style.display = 'block';
        }
    }

    // Toggle cart widget visibility
    toggleCart() {
        const cartWidget = document.getElementById('cartWidget');
        if (cartWidget) {
            cartWidget.classList.toggle('show');
        }
    }

    // Show cart message/notification
    showCartMessage(message, type = 'info') {
        // Create or update notification element
        let notification = document.getElementById('cartNotification');
        
        if (!notification) {
            notification = document.createElement('div');
            notification.id = 'cartNotification';
            notification.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                padding: 15px 20px;
                border-radius: 8px;
                color: white;
                font-weight: 600;
                z-index: 10000;
                transform: translateX(100%);
                transition: transform 0.3s ease;
                max-width: 300px;
            `;
            document.body.appendChild(notification);
        }

        // Set message and styling based on type
        notification.textContent = message;
        
        const colors = {
            success: '#27ae60',
            error: '#e74c3c',
            info: '#3498db'
        };
        
        notification.style.backgroundColor = colors[type] || colors.info;

        // Show notification
        requestAnimationFrame(() => {
            notification.style.transform = 'translateX(0)';
        });

        // Hide notification after 3 seconds
        setTimeout(() => {
            notification.style.transform = 'translateX(100%)';
        }, 3000);
    }

    // Send cart context to LLM for enhanced recommendations
    async sendCartToLLM(userMessage) {
        try {
            const cartSummary = this.cart.map(item => 
                `${item.quantity}x ${item.name} ($${item.price})`
            ).join(', ');

            const response = await fetch(this.apiEndpoints.llmInteraction, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    message: userMessage,
                    cart_context: cartSummary,
                    cart_total: this.getCartTotal()
                })
            });

            if (!response.ok) {
                throw new Error('Failed to send cart to LLM');
            }

            return await response.json();

        } catch (error) {
            console.error('Error sending cart to LLM:', error);
            return null;
        }
    }

    // Get cart total
    getCartTotal() {
        return this.cart.reduce((total, item) => total + (item.price * item.quantity), 0);
    }

    // Get cart summary for display
    getCartSummary() {
        if (this.cart.length === 0) return 'Your cart is empty';
        
        const itemsText = this.cart.map(item => 
            `${item.quantity}x ${item.name} - $${(item.price * item.quantity).toFixed(2)}`
        ).join('\n');
        
        return `${itemsText}\n\nTotal: $${this.getCartTotal().toFixed(2)}`;
    }

    // Bind event listeners
    bindEvents() {
        // Close cart when clicking outside
        document.addEventListener('click', (e) => {
            const cartWidget = document.getElementById('cartWidget');
            const cartToggle = document.querySelector('.cart-toggle');
            
            if (cartWidget && cartWidget.classList.contains('show') && 
                !cartWidget.contains(e.target) && 
                !cartToggle?.contains(e.target)) {
                cartWidget.classList.remove('show');
            }
        });

        // Handle escape key to close cart
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const cartWidget = document.getElementById('cartWidget');
                if (cartWidget?.classList.contains('show')) {
                    cartWidget.classList.remove('show');
                }
            }
        });
    }

    // Revert cart changes (for error handling)
    revertCartChange() {
        this.cart = this.loadCart();
        this.updateCartUI();
    }
}

// Global functions for template usage
let cartSystem = null;

function initializeCart(restaurantId) {
    cartSystem = new RestaurantCart(restaurantId);
}

function addToCart(itemId, itemName, itemPrice, quantity = 1) {
    if (cartSystem) {
        cartSystem.addItem(itemId, itemName, itemPrice, quantity);
    }
}

function removeFromCart(itemId) {
    if (cartSystem) {
        cartSystem.removeItem(itemId);
    }
}

function updateCartQuantity(itemId, quantity) {
    if (cartSystem) {
        cartSystem.updateQuantity(itemId, quantity);
    }
}

function toggleCart() {
    if (cartSystem) {
        cartSystem.toggleCart();
    }
}

function clearCart() {
    if (cartSystem && confirm('Are you sure you want to clear your cart?')) {
        cartSystem.clearCart();
    }
}

function checkoutCart() {
    if (cartSystem) {
        if (cartSystem.cart.length === 0) {
            alert('Your cart is empty!');
            return;
        }
        
        alert('Cart Summary:\n\n' + cartSystem.getCartSummary() + 
              '\n\nCheckout functionality would be implemented here.');
    }
}