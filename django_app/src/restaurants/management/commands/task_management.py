"""
Django management command for background task management and monitoring.
Provides task scheduling, monitoring, and queue management.
"""
import json
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.conf import settings


class Command(BaseCommand):
    help = 'Comprehensive background task management for the restaurant app'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['status', 'schedule', 'run', 'monitor', 'health'],
            default='status',
            help='Task management action to perform'
        )
        
        parser.add_argument(
            '--task',
            type=str,
            help='Specific task name to run or schedule'
        )
        
        parser.add_argument(
            '--queue',
            type=str,
            choices=['embeddings', 'ai_processing', 'scraping', 'maintenance'],
            help='Specific queue to target'
        )
        
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Enable verbose output'
        )
        
        parser.add_argument(
            '--format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format'
        )
    
    def handle(self, *args, **options):
        """Execute task management command."""
        action = options['action']
        task_name = options.get('task')
        queue = options.get('queue')
        verbose = options['verbose']
        output_format = options['format']
        
        try:
            if action == 'status':
                self._show_task_status(queue, verbose, output_format)
            elif action == 'schedule':
                self._show_scheduled_tasks(verbose, output_format)
            elif action == 'run':
                self._run_task(task_name, verbose)
            elif action == 'monitor':
                self._monitor_tasks(queue, verbose, output_format)
            elif action == 'health':
                self._check_task_health(verbose, output_format)
                
        except Exception as e:
            raise CommandError(f'Task management failed: {str(e)}')
    
    def _show_task_status(self, queue, verbose, output_format):
        """Show current task status and queue information."""
        self.stdout.write("📋 Background Task Status")
        self.stdout.write("=" * 50)
        
        status_info = {
            'timestamp': datetime.now().isoformat(),
            'available_tasks': self._get_available_tasks(),
            'queue_info': self._get_queue_info(),
            'recent_executions': self._get_recent_task_executions()
        }
        
        if output_format == 'json':
            self.stdout.write(json.dumps(status_info, indent=2, default=str))
        else:
            self._format_status_output(status_info, verbose)
    
    def _show_scheduled_tasks(self, verbose, output_format):
        """Show scheduled periodic tasks configuration."""
        self.stdout.write("⏰ Scheduled Tasks Configuration")
        self.stdout.write("=" * 50)
        
        beat_schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', {})
        
        schedule_info = {
            'timestamp': datetime.now().isoformat(),
            'total_scheduled_tasks': len(beat_schedule),
            'tasks': {}
        }
        
        for task_name, task_config in beat_schedule.items():
            schedule_info['tasks'][task_name] = {
                'task': task_config['task'],
                'schedule': str(task_config['schedule']),
                'queue': task_config.get('options', {}).get('queue', 'default'),
                'kwargs': task_config.get('kwargs', {}),
                'enabled': True  # In a real implementation, you'd check if the task is enabled
            }
        
        if output_format == 'json':
            self.stdout.write(json.dumps(schedule_info, indent=2, default=str))
        else:
            self._format_schedule_output(schedule_info, verbose)
    
    def _run_task(self, task_name, verbose):
        """Run a specific task manually."""
        if not task_name:
            raise CommandError("Task name is required when using --action run")
        
        self.stdout.write(f"🚀 Running Task: {task_name}")
        self.stdout.write("=" * 50)
        
        # Map of available tasks
        available_tasks = {
            'cleanup_old_images': 'restaurants.tasks.cleanup_old_images',
            'batch_process_pending_images': 'restaurants.tasks.batch_process_pending_images',
            'batch_update_recent_embeddings': 'restaurants.tasks.batch_update_recent_embeddings',
            'warm_popular_restaurant_cache': 'restaurants.tasks.warm_popular_restaurant_cache',
            'system_health_check': 'restaurants.tasks.system_health_check',
        }\n        \n        if task_name not in available_tasks:\n            available_task_names = list(available_tasks.keys())\n            raise CommandError(f\"Unknown task '{task_name}'. Available tasks: {', '.join(available_task_names)}\")\n        \n        try:\n            # Import and run the task\n            from restaurants.tasks import (\n                cleanup_old_images,\n                batch_process_pending_images,\n                batch_update_recent_embeddings,\n                warm_popular_restaurant_cache,\n                system_health_check\n            )\n            \n            task_functions = {\n                'cleanup_old_images': cleanup_old_images,\n                'batch_process_pending_images': batch_process_pending_images,\n                'batch_update_recent_embeddings': batch_update_recent_embeddings,\n                'warm_popular_restaurant_cache': warm_popular_restaurant_cache,\n                'system_health_check': system_health_check,\n            }\n            \n            task_function = task_functions[task_name]\n            \n            self.stdout.write(f\"Starting task: {task_name}...\")\n            start_time = datetime.now()\n            \n            # Run the task synchronously\n            result = task_function()\n            \n            end_time = datetime.now()\n            execution_time = (end_time - start_time).total_seconds()\n            \n            self.stdout.write(self.style.SUCCESS(f\"✅ Task completed successfully in {execution_time:.2f} seconds\"))\n            \n            if verbose and result:\n                self.stdout.write(f\"\\nTask Result:\")\n                self.stdout.write(json.dumps(result, indent=2, default=str))\n                \n        except Exception as e:\n            self.stdout.write(self.style.ERROR(f\"❌ Task failed: {str(e)}\"))\n            raise\n    \n    def _monitor_tasks(self, queue, verbose, output_format):\n        \"\"\"Monitor task execution and performance.\"\"\"\n        self.stdout.write(\"📊 Task Monitoring\")\n        self.stdout.write(\"=\" * 50)\n        \n        monitor_info = {\n            'timestamp': datetime.now().isoformat(),\n            'monitoring_period': '24 hours',\n            'queue_stats': self._get_queue_statistics(),\n            'task_performance': self._get_task_performance_metrics(),\n            'alerts': self._check_task_alerts()\n        }\n        \n        if output_format == 'json':\n            self.stdout.write(json.dumps(monitor_info, indent=2, default=str))\n        else:\n            self._format_monitor_output(monitor_info, verbose)\n    \n    def _check_task_health(self, verbose, output_format):\n        \"\"\"Check health of task system and queues.\"\"\"\n        self.stdout.write(\"🏥 Task System Health Check\")\n        self.stdout.write(\"=\" * 50)\n        \n        health_info = {\n            'timestamp': datetime.now().isoformat(),\n            'overall_status': 'healthy',\n            'components': {},\n            'recommendations': []\n        }\n        \n        # Check Celery broker connectivity\n        try:\n            from celery import current_app\n            \n            # Test broker connection\n            broker_connection = current_app.broker_connection()\n            broker_connection.ensure_connection(max_retries=3)\n            \n            health_info['components']['broker'] = {\n                'status': 'healthy',\n                'type': 'redis',\n                'url': settings.CELERY_BROKER_URL\n            }\n            \n        except Exception as e:\n            health_info['components']['broker'] = {\n                'status': 'unhealthy',\n                'error': str(e)\n            }\n            health_info['overall_status'] = 'degraded'\n        \n        # Check result backend connectivity\n        try:\n            from celery import current_app\n            \n            # Test result backend\n            result_backend = current_app.backend\n            \n            health_info['components']['result_backend'] = {\n                'status': 'healthy',\n                'type': 'redis',\n                'url': settings.CELERY_RESULT_BACKEND\n            }\n            \n        except Exception as e:\n            health_info['components']['result_backend'] = {\n                'status': 'unhealthy',\n                'error': str(e)\n            }\n            health_info['overall_status'] = 'degraded'\n        \n        # Check task registration\n        try:\n            from celery import current_app\n            registered_tasks = list(current_app.tasks.keys())\n            restaurant_tasks = [task for task in registered_tasks if 'restaurants.tasks' in task]\n            \n            health_info['components']['task_registration'] = {\n                'status': 'healthy',\n                'total_tasks': len(registered_tasks),\n                'restaurant_tasks': len(restaurant_tasks)\n            }\n            \n        except Exception as e:\n            health_info['components']['task_registration'] = {\n                'status': 'unhealthy',\n                'error': str(e)\n            }\n        \n        # Add recommendations based on health status\n        if health_info['overall_status'] == 'degraded':\n            health_info['recommendations'].append('Check Redis connectivity and configuration')\n            health_info['recommendations'].append('Verify Celery worker processes are running')\n        \n        if output_format == 'json':\n            self.stdout.write(json.dumps(health_info, indent=2, default=str))\n        else:\n            self._format_health_output(health_info, verbose)\n    \n    def _get_available_tasks(self):\n        \"\"\"Get list of available background tasks.\"\"\"\n        return [\n            'update_restaurant_embeddings',\n            'process_image_ai_categorization', \n            'scrape_restaurant_images_task',\n            'trigger_document_embedding_on_scrape',\n            'cleanup_old_images',\n            'batch_process_pending_images',\n            'batch_update_recent_embeddings',\n            'warm_popular_restaurant_cache',\n            'system_health_check'\n        ]\n    \n    def _get_queue_info(self):\n        \"\"\"Get queue configuration information.\"\"\"\n        task_routes = getattr(settings, 'CELERY_TASK_ROUTES', {})\n        \n        queue_info = {\n            'configured_queues': ['embeddings', 'ai_processing', 'scraping', 'maintenance'],\n            'task_routing': task_routes,\n            'default_queue': 'celery'  # Celery default\n        }\n        \n        return queue_info\n    \n    def _get_recent_task_executions(self):\n        \"\"\"Get information about recent task executions.\"\"\"\n        # This would typically query a task result backend or monitoring system\n        # For now, return placeholder data\n        return {\n            'last_24_hours': {\n                'total_executed': 'unknown',\n                'successful': 'unknown', \n                'failed': 'unknown',\n                'note': 'Task execution monitoring requires Celery result backend analysis'\n            }\n        }\n    \n    def _get_queue_statistics(self):\n        \"\"\"Get queue statistics and metrics.\"\"\"\n        # This would typically use Celery inspection APIs\n        return {\n            'embeddings': {'pending': 'unknown', 'active': 'unknown'},\n            'ai_processing': {'pending': 'unknown', 'active': 'unknown'},\n            'scraping': {'pending': 'unknown', 'active': 'unknown'},\n            'maintenance': {'pending': 'unknown', 'active': 'unknown'},\n            'note': 'Queue statistics require Celery inspection API'\n        }\n    \n    def _get_task_performance_metrics(self):\n        \"\"\"Get task performance metrics.\"\"\"\n        return {\n            'average_execution_time': 'unknown',\n            'success_rate': 'unknown',\n            'most_frequent_failures': 'unknown',\n            'note': 'Performance metrics require task result monitoring'\n        }\n    \n    def _check_task_alerts(self):\n        \"\"\"Check for task-related alerts or issues.\"\"\"\n        alerts = []\n        \n        # Check for pending images that need AI processing\n        try:\n            from restaurants.models import RestaurantImage\n            pending_count = RestaurantImage.objects.filter(processing_status='pending').count()\n            \n            if pending_count > 100:\n                alerts.append({\n                    'level': 'warning',\n                    'message': f'{pending_count} images pending AI processing',\n                    'recommendation': 'Consider running batch_process_pending_images task'\n                })\n                \n        except Exception:\n            pass\n        \n        # Check for old failed images\n        try:\n            from restaurants.models import RestaurantImage\n            from datetime import timedelta\n            cutoff = timezone.now() - timedelta(days=30)\n            \n            old_failed_count = RestaurantImage.objects.filter(\n                processing_status='failed',\n                created_at__lt=cutoff\n            ).count()\n            \n            if old_failed_count > 50:\n                alerts.append({\n                    'level': 'info',\n                    'message': f'{old_failed_count} old failed images can be cleaned up',\n                    'recommendation': 'Consider running cleanup_old_images task'\n                })\n                \n        except Exception:\n            pass\n        \n        return alerts\n    \n    def _format_status_output(self, status_info, verbose):\n        \"\"\"Format task status output for text display.\"\"\"\n        self.stdout.write(f\"\\n📋 Available Tasks ({len(status_info['available_tasks'])})\")\n        for task in status_info['available_tasks']:\n            self.stdout.write(f\"  • {task}\")\n        \n        self.stdout.write(f\"\\n🔄 Queue Configuration\")\n        queue_info = status_info['queue_info']\n        for queue in queue_info['configured_queues']:\n            self.stdout.write(f\"  • {queue}\")\n        \n        if verbose:\n            self.stdout.write(f\"\\n📊 Recent Executions\")\n            recent = status_info['recent_executions']['last_24_hours']\n            self.stdout.write(f\"  Total: {recent['total_executed']}\")\n            self.stdout.write(f\"  Note: {recent['note']}\")\n    \n    def _format_schedule_output(self, schedule_info, verbose):\n        \"\"\"Format scheduled tasks output for text display.\"\"\"\n        self.stdout.write(f\"\\n⏰ Scheduled Tasks ({schedule_info['total_scheduled_tasks']})\")\n        \n        for task_name, task_info in schedule_info['tasks'].items():\n            status_icon = \"✅\" if task_info['enabled'] else \"❌\"\n            self.stdout.write(f\"\\n{status_icon} {task_name}\")\n            self.stdout.write(f\"  Task: {task_info['task']}\")\n            self.stdout.write(f\"  Schedule: {task_info['schedule']}\")\n            self.stdout.write(f\"  Queue: {task_info['queue']}\")\n            \n            if verbose and task_info['kwargs']:\n                self.stdout.write(f\"  Args: {task_info['kwargs']}\")\n    \n    def _format_monitor_output(self, monitor_info, verbose):\n        \"\"\"Format monitoring output for text display.\"\"\"\n        alerts = monitor_info['alerts']\n        \n        if alerts:\n            self.stdout.write(f\"\\n🚨 Alerts ({len(alerts)})\")\n            for alert in alerts:\n                level_icon = \"⚠️\" if alert['level'] == 'warning' else \"ℹ️\"\n                self.stdout.write(f\"  {level_icon} {alert['message']}\")\n                if verbose:\n                    self.stdout.write(f\"    → {alert['recommendation']}\")\n        else:\n            self.stdout.write(f\"\\n✅ No alerts detected\")\n        \n        if verbose:\n            self.stdout.write(f\"\\n📊 Queue Statistics\")\n            queue_stats = monitor_info['queue_stats']\n            self.stdout.write(f\"  Note: {queue_stats['note']}\")\n    \n    def _format_health_output(self, health_info, verbose):\n        \"\"\"Format health check output for text display.\"\"\"\n        overall_status = health_info['overall_status']\n        \n        if overall_status == 'healthy':\n            status_style = self.style.SUCCESS\n            status_icon = \"✅\"\n        else:\n            status_style = self.style.WARNING\n            status_icon = \"⚠️\"\n        \n        self.stdout.write(f\"\\n{status_icon} Overall Status: {status_style(overall_status.upper())}\")\n        \n        self.stdout.write(f\"\\n🔧 Components\")\n        for component, info in health_info['components'].items():\n            status = info['status']\n            if status == 'healthy':\n                self.stdout.write(f\"  ✅ {component}: {status}\")\n            else:\n                self.stdout.write(f\"  ❌ {component}: {status}\")\n                if 'error' in info:\n                    self.stdout.write(f\"    Error: {info['error']}\")\n        \n        recommendations = health_info['recommendations']\n        if recommendations:\n            self.stdout.write(f\"\\n💡 Recommendations\")\n            for i, rec in enumerate(recommendations, 1):\n                self.stdout.write(f\"  {i}. {rec}\")