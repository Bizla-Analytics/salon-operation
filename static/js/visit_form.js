(function () {
  var orderInput = document.getElementById("id_service_order");
  var checks = document.querySelectorAll('input[name="services"]');
  var list = document.getElementById("selected-services");
  var empty = document.getElementById("empty-order");
  var search = document.getElementById("service-search");
  var picker = document.getElementById("service-select");
  var addButton = document.getElementById("add-service");
  var addFirstButton = document.getElementById("add-service-first");
  var count = document.getElementById("selection-count");
  var services = [];
  var order = [];

  function cleanText(value) {
    return (value || "").replace(/^\s+|\s+$/g, "");
  }

  function findService(id) {
    for (var i = 0; i < services.length; i += 1) {
      if (services[i].id === id) {
        return services[i];
      }
    }
    return null;
  }

  function orderContains(id) {
    for (var i = 0; i < order.length; i += 1) {
      if (order[i] === id) {
        return true;
      }
    }
    return false;
  }

  for (var checkIndex = 0; checkIndex < checks.length; checkIndex += 1) {
    var check = checks[checkIndex];
    var labelNode = check.parentNode.querySelector(".service-choice-label");
    services.push({
      id: check.value,
      label: cleanText(labelNode.textContent || labelNode.innerText),
      check: check
    });
  }

  var savedOrder = (orderInput.value || "").split(",");
  for (var savedIndex = 0; savedIndex < savedOrder.length; savedIndex += 1) {
    if (savedOrder[savedIndex]) {
      order.push(savedOrder[savedIndex]);
    }
  }
  for (var serviceIndex = 0; serviceIndex < services.length; serviceIndex += 1) {
    if (services[serviceIndex].check.checked && !orderContains(services[serviceIndex].id)) {
      order.push(services[serviceIndex].id);
    }
  }

  function selectedService() {
    return findService(picker.value);
  }

  function renderPicker() {
    var query = cleanText(search.value).toLowerCase();
    var previous = picker.value;
    var firstMatch = "";

    while (picker.options.length) {
      picker.remove(0);
    }
    var prompt = document.createElement("option");
    prompt.value = "";
    prompt.text = "Choose a service";
    picker.add(prompt);

    for (var i = 0; i < services.length; i += 1) {
      var service = services[i];
      if (service.check.checked || service.label.toLowerCase().indexOf(query) === -1) {
        continue;
      }
      var option = document.createElement("option");
      option.value = service.id;
      option.text = service.label;
      picker.add(option);
      if (!firstMatch) {
        firstMatch = service.id;
      }
    }

    var previousService = findService(previous);
    if (previousService && !previousService.check.checked) {
      picker.value = previous;
    }
    if (!picker.value && query && firstMatch) {
      picker.value = firstMatch;
    }
    addButton.disabled = !selectedService();
    addFirstButton.disabled = !selectedService();
  }

  function moveService(index, direction) {
    var target = index + direction;
    if (target < 0 || target >= order.length) {
      return;
    }
    var held = order[index];
    order[index] = order[target];
    order[target] = held;
    renderOrder();
  }

  function removeService(id) {
    var service = findService(id);
    var revised = [];
    if (service) {
      service.check.checked = false;
    }
    for (var i = 0; i < order.length; i += 1) {
      if (order[i] !== id) {
        revised.push(order[i]);
      }
    }
    order = revised;
    renderOrder();
    renderPicker();
  }

  function orderButton(text, label, disabled, handler, className) {
    var button = document.createElement("button");
    button.type = "button";
    button.appendChild(document.createTextNode(text));
    button.setAttribute("aria-label", label);
    button.disabled = disabled;
    if (className) {
      button.className = className;
    }
    button.onclick = handler;
    return button;
  }

  function renderOrder() {
    var valid = [];
    for (var i = 0; i < order.length; i += 1) {
      var orderedService = findService(order[i]);
      if (orderedService && orderedService.check.checked) {
        valid.push(order[i]);
      }
    }
    order = valid;
    orderInput.value = order.join(",");
    while (list.firstChild) {
      list.removeChild(list.firstChild);
    }
    empty.style.display = order.length ? "none" : "block";
    count.textContent = order.length + " selected";

    for (var position = 0; position < order.length; position += 1) {
      (function (itemIndex) {
        var service = findService(order[itemIndex]);
        var row = document.createElement("li");
        var number = document.createElement("b");
        var name = document.createElement("span");
        number.appendChild(document.createTextNode(itemIndex + 1));
        name.appendChild(document.createTextNode(service.label));
        row.appendChild(number);
        row.appendChild(name);
        row.appendChild(
          orderButton("Up", "Move up", itemIndex === 0, function () {
            moveService(itemIndex, -1);
          })
        );
        row.appendChild(
          orderButton("Down", "Move down", itemIndex === order.length - 1, function () {
            moveService(itemIndex, 1);
          })
        );
        row.appendChild(
          orderButton("Remove", "Remove service", false, function () {
            removeService(service.id);
          }, "remove-service")
        );
        list.appendChild(row);
      }(position));
    }
  }

  function addService(position) {
    var service = selectedService();
    if (!service) {
      return;
    }
    service.check.checked = true;
    if (!orderContains(service.id)) {
      if (position === "first") {
        order.unshift(service.id);
      } else {
        order.push(service.id);
      }
    }
    search.value = "";
    renderOrder();
    renderPicker();
    search.focus();
  }

  addButton.onclick = function () {
    addService("last");
  };
  addFirstButton.onclick = function () {
    addService("first");
  };
  picker.onchange = function () {
    addButton.disabled = !selectedService();
    addFirstButton.disabled = !selectedService();
  };
  search.oninput = renderPicker;
  search.onkeyup = renderPicker;
  search.onchange = renderPicker;

  renderOrder();
  renderPicker();
}());
