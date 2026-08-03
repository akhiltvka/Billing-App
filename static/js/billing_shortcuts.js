/**
 * billing_shortcuts.js
 * ---------------------------------------------------------------
 * Keyboard-shortcut module for the MPI billing screen.
 *
 * DESIGN GOAL: a trained cashier should complete an entire sale
 * without touching the mouse, even during rush hour.
 *
 * HOW TO INTEGRATE
 * -----------------
 * 1. Include this file on your billing.html template:
 *      <script src="{{ url_for('static', filename='js/billing_shortcuts.js') }}"></script>
 *
 * 2. At the bottom of your billing page's own script, call:
 *
 *      BillingShortcuts.init({
 *        onNewBill:        () => { ... your existing "start new bill" fn ... },
 *        onSearchItem:     () => { document.getElementById('item-search').focus(); },
 *        onSearchCustomer: () => { document.getElementById('customer-search').focus(); },
 *        onBillDiscount:   () => { openBillDiscountModal(); },
 *        onHoldBill:       () => { holdCurrentBill(); },        // AJAX to /billing/hold
 *        onRecallBill:     () => { openHeldBillsList(); },      // AJAX to /billing/held
 *        onChangePayment:  () => { cyclePaymentMode(); },
 *        onSaveAndPrint:   () => { submitBill({ print: true }); },
 *        onSaveOnly:       () => { submitBill({ print: false }); },
 *        onOpenDrawer:     () => { fetch('/billing/open-drawer', {method:'POST'}); },
 *        onVoidBill:       () => { requestVoidWithPin(); },     // shows supervisor PIN modal
 *        onReprintLast:    () => { reprintLastInvoice(); },
 *        onQuickCode:      (code, qty) => { addItemByCode(code, qty); },
 *        onLineDiscount:   () => { openLineDiscountModal(getSelectedRow()); },
 *        onQtyChange:      (delta) => { adjustQtyOnSelectedRow(delta); },
 *        onDeleteLine:     () => { removeSelectedRow(); },
 *        onNewCustomer:    () => { openQuickAddCustomerModal(); },
 *        onDaySummary:     () => { openDaySummaryPanel(); },
 *        onGroupJump:      (n) => { jumpToItemGroup(n); },      // n = 1..9
 *        isModalOpen:      () => { return document.querySelector('.modal.open') !== null; },
 *        getSelectedRow:   () => { return currentSelectedRowElement; }, // your own tracker
 *      });
 *
 * All callbacks are optional — if you don't pass one, that shortcut
 * is simply a no-op. This lets you wire it up incrementally.
 *
 * QUICK-CODE ENTRY
 * -----------------
 * Typing "1234*3" then Enter in the quick-entry field (or anywhere
 * global capture is active) calls onQuickCode('1234', 3).
 * Typing just "1234" then Enter calls onQuickCode('1234', 1).
 *
 * NOTHING in this file makes network calls itself — it only
 * captures keys and calls the callbacks you supply. Keeps it
 * framework-agnostic and safe to drop into any Flask/Jinja page.
 * ---------------------------------------------------------------
 */

const BillingShortcuts = (function () {
  'use strict';

  const DEFAULT_KEYMAP = {
    'F1': 'onNewBill',
    'F2': 'onSearchItem',
    'F3': 'onSearchCustomer',
    'F4': 'onBillDiscount',
    'F5': 'onHoldBill',
    'F6': 'onRecallBill',
    'F7': 'onChangePayment',
    'F8': 'onSaveAndPrint',
    'F9': 'onSaveOnly',
    'F10': 'onOpenDrawer',
    'F12': 'onVoidBill',
  };

  // Ctrl-combo shortcuts (checked separately since browsers reserve
  // some plain Ctrl+letter combos; these are the ones that are safe
  // to override inside a focused web app / kiosk window)
  const CTRL_KEYMAP = {
    '1': 'onBillSummary',
    's': 'onSaveAndPrint',
    'p': 'onReprintLast',
    'q': '__quickCodeFocus', // focuses the quick-code field; actual add happens on Enter
    'f': 'onSearchItem',
    'd': 'onLineDiscount',
    'n': 'onNewCustomer',
    'h': 'onRecallBill',
    'b': 'onHoldBill',
    'g': 'onDaySummary',
  };

  let callbacks = {};
  let quickCodeBuffer = '';
  let quickCodeFieldId = null;
  let initialized = false;

  function isTypingInTextField(target) {
    if (!target) return false;
    const tag = target.tagName;
    if (tag === 'TEXTAREA') return true;
    if (tag === 'INPUT') {
      const type = (target.getAttribute('type') || 'text').toLowerCase();
      return ['text', 'search', 'number', 'tel', 'email', 'password'].includes(type);
    }
    if (target.isContentEditable) return true;
    return false;
  }

  function call(name, ...args) {
    if (typeof callbacks[name] === 'function') {
      callbacks[name](...args);
      return true;
    }
    return false;
  }

  function modalOpen() {
    if (typeof callbacks.isModalOpen === 'function') {
      return !!callbacks.isModalOpen();
    }
    return false;
  }

  /**
   * Handles the "1234*3" style quick-code pattern.
   * Called when Enter is pressed inside the quick-code input field
   * (id supplied via init options, or any field with
   * data-role="quick-code" if no id given).
   */
  function handleQuickCodeSubmit(rawValue) {
    const value = (rawValue || '').trim();
    if (!value) return;
    const parts = value.split('*');
    const code = parts[0].trim();
    const qty = parts.length > 1 ? parseFloat(parts[1]) || 1 : 1;
    if (code) {
      call('onQuickCode', code, qty);
    }
  }

  function attachQuickCodeField() {
    const field = quickCodeFieldId
      ? document.getElementById(quickCodeFieldId)
      : document.querySelector('[data-role="quick-code"]');
    if (!field) return;
    field.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleQuickCodeSubmit(field.value);
        field.value = '';
      }
    });
  }

  function handleGlobalKeydown(e) {
    if (!initialized) return;

    // Esc always allowed, even inside inputs/modals — closes things.
    if (e.key === 'Escape') {
      call('onEscape');
      return;
    }

    // While a modal (discount, PIN, held-bills list, etc.) is open,
    // let it handle its own keys — don't fire billing shortcuts underneath it.
    if (modalOpen()) return;

    const target = e.target;
    const typingInField = isTypingInTextField(target);

    // Plain F-keys work everywhere, even while typing in a field
    // (a cashier mid-way through typing a rate might still need F8 to save).
    if (DEFAULT_KEYMAP[e.key]) {
      e.preventDefault();
      call(DEFAULT_KEYMAP[e.key]);
      return;
    }

    // Ctrl-combos
    if (e.ctrlKey && !e.altKey) {
      const k = e.key.toLowerCase();
      if (CTRL_KEYMAP[k]) {
        e.preventDefault();
        if (CTRL_KEYMAP[k] === '__quickCodeFocus') {
          const field = quickCodeFieldId
            ? document.getElementById(quickCodeFieldId)
            : document.querySelector('[data-role="quick-code"]');
          if (field) field.focus();
        } else {
          call(CTRL_KEYMAP[k]);
        }
        return;
      }
    }

    // Alt-combos (Alt+C / Alt+N -> Quick Add Customer; Alt+1..9 -> jump to group)
    if (e.altKey && !e.ctrlKey) {
      const k = e.key.toLowerCase();
      if (k === 'c' || k === 'n') {
        e.preventDefault();
        call('onNewCustomer');
        return;
      }
      if (/^[1-9]$/.test(e.key)) {
        e.preventDefault();
        call('onGroupJump', parseInt(e.key, 10));
        return;
      }
    }

    // The remaining shortcuts only fire when NOT typing in a text field,
    // so that +, -, Delete, Enter etc. don't hijack normal typing.
    if (typingInField) return;

    switch (e.key) {
      case '+':
        e.preventDefault();
        call('onQtyChange', 1);
        break;
      case '-':
        e.preventDefault();
        call('onQtyChange', -1);
        break;
      case 'Delete':
        e.preventDefault();
        call('onDeleteLine');
        break;
      default:
        break;
    }
  }

  function init(userCallbacks, options) {
    callbacks = userCallbacks || {};
    options = options || {};
    quickCodeFieldId = options.quickCodeFieldId || null;

    document.addEventListener('keydown', handleGlobalKeydown, true);
    attachQuickCodeField();

    initialized = true;
    console.info('[BillingShortcuts] initialized. Press F1 for a new bill.');
  }

  function destroy() {
    document.removeEventListener('keydown', handleGlobalKeydown, true);
    initialized = false;
  }

  /** Returns the current keymap so you can render a cheat-sheet in the UI. */
  function getKeymapReference() {
    return {
      'F1': 'New bill',
      'F2': 'Search item',
      'F3': 'Search customer',
      'F4': 'Bill-level discount',
      'F5': 'Hold bill',
      'F6': 'Recall held bill',
      'F7': 'Change payment mode',
      'F8': 'Save & print',
      'F9': 'Save without printing',
      'F10': 'Open cash drawer',
      'F12': 'Void bill (needs supervisor PIN)',
      'Ctrl+1': 'Bill Summary popup',
      'Ctrl+P': 'Reprint last invoice',
      'Ctrl+Q': 'Focus quick-code entry',
      'Ctrl+D': 'Line-item discount',
      'Ctrl+N': 'Quick-add customer',
      'Ctrl+G': "Today's summary",
      'Alt+1..9': 'Jump to item group 1-9',
      '+ / -': 'Increase/decrease qty on selected row',
      'Delete': 'Remove selected line',
      'Esc': 'Close modal / cancel input',
      'Quick-code field: 1234*3 + Enter': 'Add item 1234, qty 3',
    };
  }

  return { init, destroy, getKeymapReference };
})();
