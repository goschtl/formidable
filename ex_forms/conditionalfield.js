/**
 * Conditional Fields jQuery Module
 * Handles dynamic field visibility based on conditions
 */
(function($) {
    'use strict';

    const ConditionalFields = {
        // Debug flag - set to false in production
        debug: false,

        /**
         * Initialize the conditional fields module
         */
        init: function() {
            if (this.debug) console.log('ConditionalFields.init() aufgerufen');
            this.bindEvents();
            this.evaluateAllConditions();
            this.evaluateAllConditionalOptions();
        },

        /**
         * Bind events for conditional field evaluation
         */
        bindEvents: function() {
            // Listen for changes on any form field to evaluate conditions
            // Use 'change' for most fields, 'input' only for text fields that need real-time updates
            $(document).on('change', 'input, select, textarea', function() {
                ConditionalFields.evaluateArrayConditions($(this));
                ConditionalFields.evaluateAllConditionalOptions();
            });

            // Listen for clicks on the "add item" button
            $(document).on('click', '.deform-seq-add', function() {
                setTimeout(() => {
                    ConditionalFields.evaluateAllConditions();
                }, 100); // Delay to allow the new item to be fully rendered
            });

            // Use MutationObserver for more reliable detection of new array items
            if (typeof MutationObserver !== 'undefined') {
                const observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        mutation.addedNodes.forEach(function(node) {
                            if (node.nodeType === 1 && ($(node).hasClass('deform-seq-item') || $(node).find('.deform-seq-item').length > 0)) {
                                setTimeout(() => {
                                    ConditionalFields.evaluateAllConditions();
                                }, 50);
                            }
                        });
                    });
                });
                observer.observe(document.body, { childList: true, subtree: true });
            }
        },

        /**
         * Evaluate all conditional fields on the page
         */
        evaluateAllConditions: function() {
            // Look for both .conditional-field and [data-conditions] elements
            const $conditionalElements = $('.conditional-field, [data-conditions]');
            if (this.debug) console.log('Found conditional fields:', $conditionalElements.length);
            $conditionalElements.each(function() {
                const $field = $(this);
                // Check if this field is inside an array item (deform sequence)
                const $arrayItem = $field.closest('.deform-seq-item');
                if ($arrayItem.length > 0) {
                    // Pass the array item as scope
                    ConditionalFields.evaluateFieldConditions($field, $arrayItem);
                } else {
                    // Not in an array, evaluate without scope
                    ConditionalFields.evaluateFieldConditions($field);
                }
            });
        },

        /**
         * Evaluate conditions for array fields - scope to current array item
         */
        evaluateArrayConditions: function($changedField) {
            // Find the array item container that contains this field
            const $arrayItem = $changedField.closest('.deform-seq-item');

            if ($arrayItem.length > 0) {
                // Only evaluate conditions within this array item
                const $conditionalElements = $arrayItem.find('.conditional-field, [data-conditions]');
                if (this.debug) console.log('Found conditional fields in array item:', $conditionalElements.length);
                $conditionalElements.each(function() {
                    const $field = $(this);
                    ConditionalFields.evaluateFieldConditions($field, $arrayItem);
                });
            } else {
                // Not in an array, evaluate all conditions
                this.evaluateAllConditions();
            }
        },

        /**
         * Evaluate conditions for a specific field
         */
        evaluateFieldConditions: function($field, $scope) {
            if (this.debug) console.log('Processing conditional field:', $field[0]);
            let conditionsData = $field.data('conditions');

            // If no conditions on the field itself, check child elements
            if (!conditionsData) {
                const $conditionChild = $field.find('[data-conditions]').first();
                if ($conditionChild.length > 0) {
                    conditionsData = $conditionChild.data('conditions');
                    if (this.debug) console.log('Found conditions on child element:', conditionsData);
                }
            }

            if (this.debug) console.log('Final conditions data:', conditionsData);

            if (conditionsData) {
                try {
                    let conditions;
                    if (typeof conditionsData === 'string') {
                        // Legacy single-quote format from old templates
                        try {
                            const fixedJson = conditionsData.replace(/'/g, '"');
                            conditions = JSON.parse(fixedJson);
                        } catch (e) {
                            console.warn('Failed to parse conditions:', conditionsData, e);
                            return;
                        }
                    } else {
                        // Already parsed by jQuery (proper JSON with &quot; encoding)
                        conditions = conditionsData;
                    }
                    if (this.debug) console.log('Parsed conditions:', conditions);

                    // Handle both old format {conditions: [...], logic: 'and'} and new format {field: '', operator: '', value: ''}
                    let isVisible;
                    if (conditions.conditions && Array.isArray(conditions.conditions)) {
                        // Old format
                        isVisible = ConditionalFields.evaluateConditions(conditions, $scope);
                    } else if (conditions.field && conditions.operator) {
                        // New format - single condition
                        isVisible = ConditionalFields.evaluateSingleCondition(conditions, $scope);
                    } else {
                        console.warn('Unknown condition format:', conditions);
                        isVisible = true;
                    }
                    ConditionalFields.toggleField($field, isVisible);
                } catch (e) {
                    console.warn('Invalid conditions data:', conditionsData, e);
                }
            }
        },

        /**
         * Evaluate a set of conditions with logic (and/or)
         * @param {Object} conditionsObj - Object containing conditions array and logic
         * @param {jQuery} $scope - Scope to search for fields (for array items)
         * @returns {boolean} - Whether conditions are met
         */
        evaluateConditions: function(conditionsObj, $scope) {
            const { conditions, logic = 'and' } = conditionsObj;

            if (!Array.isArray(conditions) || conditions.length === 0) {
                return true;
            }

            const results = conditions.map(condition =>
                this.evaluateSingleCondition(condition, $scope)
            );

            return logic === 'and'
                ? results.every(result => result)
                : results.some(result => result);
        },

        /**
         * Evaluate a single condition
         * @param {Object} condition - Single condition object
         * @param {jQuery} $scope - Scope to search for fields (for array items)
         * @returns {boolean} - Whether condition is met
         */
        evaluateSingleCondition: function(condition, $scope) {
            let { field, operator, value } = condition;
            let $targetField;

            // Helper function to find deform fields
            const findDeformField = function($searchScope, fieldName) {
                // Use the provided fieldName parameter instead of the outer field variable
                const field = fieldName;
                // Try direct name match first
                let $field = $searchScope.find(`[name="${field}"]`);
                if ($field.length > 0) return $field;

                // For deform fields, look for the __start__ hidden input that contains the field name
                const $startMarker = $searchScope.find(`input[type="hidden"][name="__start__"]`).filter(function() {
                    const val = $(this).val();
                    return val && (val.startsWith(field + ':') || val === field);
                });

                if ($startMarker.length > 0) {
                    // Found the start marker, now find the actual input fields between __start__ and __end__
                    const $parent = $startMarker.parent();

                    // For checkboxes, find all checkbox inputs in this container (any name)
                    $field = $parent.find('input[type="checkbox"]');
                    if ($field.length > 0) return $field;

                    // For radio buttons, find all radio inputs in this container
                    $field = $parent.find('input[type="radio"]');
                    if ($field.length > 0) return $field;

                    // For select dropdowns, text inputs, and other form fields
                    $field = $parent.find('select, input:not([type="hidden"]):not([name="__start__"]):not([name="__end__"]), textarea').first();
                    if ($field.length > 0) return $field;
                }

                return $();
            };

            if ($scope) {
                $targetField = findDeformField($scope, field);

                // If not found and field contains '.items.', extract the part after '.items.'
                if ($targetField.length === 0 && field.includes('.items.')) {
                    const afterItems = field.split('.items.')[1];
                    if (ConditionalFields.debug) console.log(`Field "${field}" not found, trying name after .items.: "${afterItems}"`);
                    field = afterItems;
                    $targetField = findDeformField($scope, field);
                }

                // If not found and field contains dots, try to extract the simple field name
                if ($targetField.length === 0 && field.includes('.')) {
                    const parts = field.split('.');
                    const simpleFieldName = parts[parts.length - 1];
                    if (ConditionalFields.debug) console.log(`Field "${field}" not found, trying simple name "${simpleFieldName}"`);
                    field = simpleFieldName;
                    $targetField = findDeformField($scope, field);
                }

                // If still not found in scope, try searching globally
                if ($targetField.length === 0) {
                    if (ConditionalFields.debug) console.log(`Field "${field}" not found in scope, searching globally`);
                    $targetField = findDeformField($(document), field);
                }
            } else {
                // Look globally
                $targetField = findDeformField($(document), field);
            }

            if ($targetField.length === 0) {
                console.warn(`Target field "${field}" not found anywhere`);
                return false;
            }

            // Check if the target field is disabled (hidden by another condition)
            // If so, this condition should evaluate to false (cascade hide)
            if ($targetField.prop('disabled')) {
                if (this.debug) console.log(`Target field "${field}" is disabled, cascade hiding`);
                return false;
            }

            let targetValue = this.getFieldValue($targetField, $scope);

            if (this.debug) console.log(`Condition check: "${targetValue}" ${operator} "${value}"`);

            switch (operator) {
                case 'equals':
                    // Handle array values (checkbox groups)
                    if (Array.isArray(targetValue)) {
                        return targetValue.includes(value);
                    }
                    // Handle boolean values (single checkboxes) - compare as strings
                    if (typeof targetValue === 'boolean') {
                        return targetValue.toString() === value.toString();
                    }
                    return targetValue === value;
                case 'not_equals':
                    // Handle array values (checkbox groups)
                    if (Array.isArray(targetValue)) {
                        return !targetValue.includes(value);
                    }
                    // Handle boolean values (single checkboxes) - compare as strings
                    if (typeof targetValue === 'boolean') {
                        return targetValue.toString() !== value.toString();
                    }
                    return targetValue !== value;
                case 'contains':
                    return targetValue && targetValue.toString().includes(value);
                case 'not_contains':
                    return !targetValue || !targetValue.toString().includes(value);
                case 'starts_with':
                    return targetValue && targetValue.toString().startsWith(value);
                case 'ends_with':
                    return targetValue && targetValue.toString().endsWith(value);
                case 'greater_than':
                    return parseFloat(targetValue) > parseFloat(value);
                case 'less_than':
                    return parseFloat(targetValue) < parseFloat(value);
                case 'greater_equal':
                    return parseFloat(targetValue) >= parseFloat(value);
                case 'less_equal':
                    return parseFloat(targetValue) <= parseFloat(value);
                case 'empty':
                    return !targetValue || targetValue.toString().trim() === '';
                case 'not_empty':
                    return targetValue && targetValue.toString().trim() !== '';
                case 'in':
                    return Array.isArray(value) && value.includes(targetValue);
                case 'not_in':
                    return !Array.isArray(value) || !value.includes(targetValue);
                default:
                    console.warn(`Unknown operator: ${operator}`);
                    return false;
            }
        },

        /**
         * Get value from a form field (handles different input types)
         * @param {jQuery} $field - jQuery object of the field
         * @param {jQuery} $scope - Scope to search within (for array items)
         * @returns {string|boolean|array} - Field value
         */
        getFieldValue: function($field, $scope) {
            const fieldType = $field.attr('type');
            const tagName = $field.prop('tagName').toLowerCase();
            const fieldName = $field.attr('name');

            if (fieldType === 'checkbox') {
                // Check if this is a checkbox group (multiple checkboxes with same name)
                const $allCheckboxes = $scope
                    ? $scope.find(`[name="${fieldName}"][type="checkbox"]`)
                    : $(`[name="${fieldName}"][type="checkbox"]`);

                if ($allCheckboxes.length > 1) {
                    // Multiple checkboxes - return array of checked values
                    const values = [];
                    $allCheckboxes.filter(':checked').each(function() {
                        values.push($(this).val());
                    });
                    return values;
                } else {
                    // Single checkbox - return its value if checked, empty string if unchecked
                    // This allows conditions to match on the checkbox's value attribute
                    return $field.is(':checked') ? $field.val() : '';
                }
            } else if (fieldType === 'radio') {
                if ($scope) {
                    // Look for checked radio within the scope
                    return $scope.find(`[name="${$field.attr('name')}"]:checked`).val() || '';
                } else {
                    // Global lookup as fallback
                    return $(`[name="${$field.attr('name')}"]:checked`).val() || '';
                }
            } else if (tagName === 'select') {
                return $field.val() || '';
            } else {
                return $field.val() || '';
            }
        },

        /**
         * Evaluate all conditional options on the page.
         * Finds elements with data-conditional-options and applies option visibility.
         */
        evaluateAllConditionalOptions: function() {
            const self = this;
            $('[data-conditional-options]').each(function() {
                const $field = $(this);
                let config = $field.data('conditional-options');
                if (!config) return;

                if (typeof config === 'string') {
                    try {
                        config = JSON.parse(config);
                    } catch (e) {
                        console.warn('Failed to parse conditional-options:', config, e);
                        return;
                    }
                }

                self.applyConditionalOptions($field, config);
            });
        },

        /**
         * Apply conditional option visibility for a single field.
         * Shows/hides individual checkbox/radio/select options based on source field value.
         * @param {jQuery} $field - The element with data-conditional-options
         * @param {Object} config - {source_field, default_options, rules: [{value, options}]}
         */
        applyConditionalOptions: function($field, config) {
            // Find the source field value
            const $scope = $field.closest('.deform-seq-item');
            const $searchScope = $scope.length > 0 ? $scope : $(document);

            // Find the source field using the same helper as evaluateSingleCondition
            let $sourceField = $searchScope.find('[name="' + config.source_field + '"]');
            if ($sourceField.length === 0) {
                // Try deform __start__ marker lookup
                const $startMarker = $searchScope.find('input[type="hidden"][name="__start__"]').filter(function() {
                    const val = $(this).val();
                    return val && (val.startsWith(config.source_field + ':') || val === config.source_field);
                });
                if ($startMarker.length > 0) {
                    $sourceField = $startMarker.parent().find('select, input:not([type="hidden"]):not([name="__start__"]):not([name="__end__"]), textarea').first();
                }
            }

            let sourceValue = '';
            if ($sourceField.length > 0) {
                sourceValue = this.getFieldValue($sourceField, $scope.length > 0 ? $scope : undefined);
            }

            // Find matching rule
            let visibleOptions = config.default_options || [];
            for (let i = 0; i < config.rules.length; i++) {
                const rule = config.rules[i];
                if (rule.value === sourceValue) {
                    visibleOptions = rule.options;
                    break;
                }
            }

            if (this.debug) console.log('Conditional options:', config.source_field, '=', sourceValue, '-> visible:', visibleOptions);

            // Checkbox/Radio options
            $field.find('.form-check').each(function() {
                const $check = $(this);
                const val = $check.find('input').val();
                if (visibleOptions.indexOf(val) !== -1) {
                    $check.slideDown(300);
                    $check.find('input').prop('disabled', false);
                } else {
                    $check.slideUp(300);
                    $check.find('input').prop('disabled', true).prop('checked', false);
                }
            });

            // Select options
            $field.find('select option').each(function() {
                const $opt = $(this);
                const val = $opt.val();
                if (!val) return; // skip empty/placeholder options
                if (visibleOptions.indexOf(val) !== -1) {
                    $opt.show().prop('disabled', false);
                } else {
                    $opt.hide().prop('disabled', true);
                    if ($opt.is(':selected')) {
                        $opt.prop('selected', false);
                    }
                }
            });
        },

        /**
         * Show or hide a conditional field with fade animation
         * @param {jQuery} $field - jQuery object of the field container
         * @param {boolean} isVisible - Whether field should be visible
         */
        toggleField: function($field, isVisible) {
            let $container = $field.closest('.mb-3, .col-md-6, .col-md-12, .col-12, .form-group, .field-group, .fieldset-container');
            // If no parent container found, use the field itself as the container
            if ($container.length === 0) {
                $container = $field;
            }
            if (this.debug) console.log('Toggle field - isVisible:', isVisible, 'container:', $container[0]);

            if (isVisible) {
                // Check if already visible to avoid unnecessary animations
                if ($container.is(':hidden')) {
                    $container.slideDown(300).removeClass('conditional-hidden');
                } else {
                    $container.removeClass('conditional-hidden');
                }
                // Re-enable form fields: enable all inputs (including hidden
                // __start__/__end__ markers needed by peppercorn/deform) and
                // mark visible inputs as required.
                // IMPORTANT: Skip inputs inside nested conditional fields -
                // they will be handled by their own condition evaluation.
                // Check if this container opts out of required marking
                const skipRequired = $field.attr('data-not-required') === 'true';
                if (this.debug) console.log('skipRequired:', skipRequired, 'data-not-required:', $field.attr('data-not-required'), 'field:', $field[0]);
                $container.find('input, select, textarea').each(function() {
                    const $input = $(this);
                    const $closestConditional = $input.closest('.conditional-field, [data-conditions]');
                    if ($closestConditional.length > 0 && $closestConditional[0] !== $field[0]) {
                        return; // skip - belongs to a nested conditional field
                    }
                    $input.prop('disabled', false);
                    // Check per-input: skip required if the container OR
                    // any ancestor wrapper has data-not-required="true"
                    const $notReqWrapper = $input.closest('[data-not-required="true"]');
                    const inputSkipRequired = skipRequired ||
                        ($notReqWrapper.length > 0 && $container[0].contains($notReqWrapper[0]));
                    if (!inputSkipRequired && $input.attr('type') !== 'hidden') {
                        $input.prop('required', true);
                    }
                });
                // Add required marker to field labels and legends
                $container.find('label.control-label, label.form-label, fieldset > legend').each(function() {
                    const $lbl = $(this);
                    const $closestConditional = $lbl.closest('.conditional-field, [data-conditions]');
                    if ($closestConditional.length > 0 && $closestConditional[0] !== $field[0]) {
                        return; // skip - belongs to a nested conditional field
                    }
                    const $notReqWrapper = $lbl.closest('[data-not-required="true"]');
                    const lblSkipRequired = skipRequired ||
                        ($notReqWrapper.length > 0 && $container[0].contains($notReqWrapper[0]));
                    if (!lblSkipRequired) {
                        $lbl.addClass('required');
                    }
                });
            } else {
                // Check if already hidden to avoid unnecessary animations
                if ($container.is(':visible')) {
                    $container.slideUp(300, function() {
                        $(this).addClass('conditional-hidden');
                    });
                } else {
                    $container.hide().addClass('conditional-hidden');
                }
                // Remove required marker from all labels and legends in the container
                $container.find('label.control-label, label.form-label, fieldset > legend').removeClass('required');
                // Reset all form field values to prevent stale data when
                // the container is re-shown.
                $container.find('input[type="radio"], input[type="checkbox"]').prop('checked', false);
                $container.find('input:not([type="radio"]):not([type="checkbox"]):not([type="hidden"]), textarea').val('');
                $container.find('select').each(function() {
                    $(this).prop('selectedIndex', 0);
                });
                // Disable all inputs
                $container.find('input, select, textarea').each(function() {
                    $(this).prop('disabled', true)
                        .prop('required', false)
                        .removeClass('is-invalid is-valid');
                });
            }
        }
    };

    // Auto-initialize when DOM is ready
    $(document).ready(function() {
        if (ConditionalFields.debug) console.log('Document ready - initializing ConditionalFields');
        ConditionalFields.init();
    });

    // Expose ConditionalFields globally for manual control
    window.ConditionalFields = ConditionalFields;

})(jQuery);
