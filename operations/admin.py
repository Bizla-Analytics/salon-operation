from django.contrib import admin

from .models import (
    Branch,
    Chair,
    Customer,
    Equipment,
    Feedback,
    FeedbackAnswer,
    FeedbackQuestion,
    InventoryItem,
    Invoice,
    OperationalTask,
    Profile,
    Service,
    ServiceDetail,
    SOPTask,
    SubService,
    TaskEquipment,
    TaskInventory,
    Visit,
    VisitService,
    VisitTask,
)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "active")
    search_fields = ("code", "name")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "branch", "employee_code", "active")
    list_filter = ("role", "branch", "active")


class ServiceDetailInline(admin.TabularInline):
    model = ServiceDetail
    extra = 0


class SOPInline(admin.TabularInline):
    model = SOPTask
    extra = 0


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "customer_type", "standard_duration_minutes", "active")
    search_fields = ("code", "name")
    list_filter = ("active", "category", "customer_type")
    inlines = (ServiceDetailInline, SOPInline)


class OperationalTaskInline(admin.TabularInline):
    model = OperationalTask
    extra = 0


@admin.register(SubService)
class SubServiceAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "active")
    search_fields = ("code", "name")
    inlines = (OperationalTaskInline,)


@admin.register(OperationalTask)
class OperationalTaskAdmin(admin.ModelAdmin):
    list_display = ("external_id", "name", "sub_service", "active_labour_minutes", "passive_time_minutes", "active")
    list_filter = ("active", "sub_service")
    search_fields = ("external_id", "name")


@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "base_unit", "active")
    search_fields = ("code", "name")


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "utility_type", "active")
    search_fields = ("code", "name")


@admin.register(TaskInventory)
class TaskInventoryAdmin(admin.ModelAdmin):
    list_display = ("external_id", "task", "service", "inventory", "effective_quantity", "unit", "active")
    list_filter = ("service", "active")


@admin.register(TaskEquipment)
class TaskEquipmentAdmin(admin.ModelAdmin):
    list_display = ("external_id", "task", "equipment", "equipment_usage_minutes", "utility_minutes", "active")
    list_filter = ("active", "utility_type")


@admin.register(SOPTask)
class SOPTaskAdmin(admin.ModelAdmin):
    list_display = ("service", "sequence", "phase", "task_type", "title", "required", "can_skip", "active")
    list_filter = ("service", "phase", "task_type", "active")


admin.site.register([Chair, Customer, Visit, VisitService, VisitTask, Invoice, FeedbackQuestion, Feedback, FeedbackAnswer])
admin.site.site_header = "Salon Operations Administration"
