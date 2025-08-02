"""
Django management command for comprehensive cache management.
Provides cache monitoring, invalidation, and performance analysis.
"""
import json
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.conf import settings


class Command(BaseCommand):
    help = 'Comprehensive cache management for the restaurant app'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--action',
            type=str,
            choices=['stats', 'health', 'clear', 'warm', 'analyze'],
            default='stats',
            help='Cache management action to perform'
        )
        
        parser.add_argument(
            '--cache-type',
            type=str,
            choices=['all', 'django', 'unified', 'search', 'restaurant'],
            default='all',
            help='Type of cache to manage'
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
        """Execute cache management command."""
        action = options['action']
        cache_type = options['cache_type']
        verbose = options['verbose']
        output_format = options['format']
        
        try:
            if action == 'stats':
                self._show_cache_stats(cache_type, verbose, output_format)
            elif action == 'health':
                self._check_cache_health(cache_type, verbose, output_format)
            elif action == 'clear':
                self._clear_cache(cache_type, verbose)
            elif action == 'warm':
                self._warm_cache(cache_type, verbose)
            elif action == 'analyze':
                self._analyze_cache_performance(cache_type, verbose, output_format)
                
        except Exception as e:
            raise CommandError(f'Cache management failed: {str(e)}')
    
    def _show_cache_stats(self, cache_type, verbose, output_format):
        """Show comprehensive cache statistics."""
        self.stdout.write("📊 Cache Statistics Report")
        self.stdout.write("=" * 50)
        
        stats = {}
        
        # Django cache stats
        if cache_type in ['all', 'django']:
            try:
                stats['django_cache'] = self._get_django_cache_stats()
            except Exception as e:
                stats['django_cache'] = {'error': str(e)}
        
        # Unified cache stats
        if cache_type in ['all', 'unified', 'search']:
            try:
                from restaurants.cache_integration import get_django_cache
                django_cache_integration = get_django_cache()
                stats['unified_cache'] = django_cache_integration.get_cache_stats()
            except ImportError:
                stats['unified_cache'] = {'error': 'Cache integration not available'}
            except Exception as e:
                stats['unified_cache'] = {'error': str(e)}
        
        # Consolidated cache stats
        if cache_type in ['all']:
            try:
                from restaurants.cache_strategy import get_consolidated_cache
                consolidated_cache = get_consolidated_cache()
                stats['consolidated_cache'] = consolidated_cache.get_consolidated_stats()
            except ImportError:
                stats['consolidated_cache'] = {'error': 'Consolidated cache not available'}
            except Exception as e:
                stats['consolidated_cache'] = {'error': str(e)}
        
        # Output results
        if output_format == 'json':
            self.stdout.write(json.dumps(stats, indent=2, default=str))
        else:
            self._format_stats_output(stats, verbose)
    
    def _check_cache_health(self, cache_type, verbose, output_format):
        """Perform comprehensive cache health check."""
        self.stdout.write("🏥 Cache Health Check")
        self.stdout.write("=" * 50)
        
        health_results = {}
        overall_status = 'healthy'
        
        # Django cache health
        if cache_type in ['all', 'django']:
            try:
                test_key = f"health_test_{datetime.now().timestamp()}"
                cache.set(test_key, 'test', 10)
                result = cache.get(test_key)
                cache.delete(test_key)
                
                health_results['django_cache'] = {
                    'status': 'healthy' if result == 'test' else 'unhealthy',
                    'backend': settings.CACHES['default']['BACKEND'],
                    'location': settings.CACHES['default']['LOCATION']
                }
                
                if health_results['django_cache']['status'] != 'healthy':
                    overall_status = 'degraded'
                    
            except Exception as e:
                health_results['django_cache'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                overall_status = 'critical'
        
        # Unified cache health
        if cache_type in ['all', 'unified', 'search']:
            try:
                from restaurants.cache_integration import get_django_cache
                django_cache_integration = get_django_cache()
                unified_health = django_cache_integration.cache_manager.health_check()
                health_results['unified_cache'] = unified_health
                
                if unified_health.get('status') != 'healthy':
                    overall_status = 'degraded'
                    
            except ImportError:
                health_results['unified_cache'] = {
                    'status': 'unavailable',
                    'error': 'Cache integration not available'
                }
            except Exception as e:
                health_results['unified_cache'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                overall_status = 'critical'
        
        # Consolidated cache health
        if cache_type in ['all']:
            try:
                from restaurants.cache_strategy import get_consolidated_cache
                consolidated_cache = get_consolidated_cache()
                consolidated_health = consolidated_cache.health_check()
                health_results['consolidated_cache'] = consolidated_health
                
                if consolidated_health.get('status') != 'healthy':
                    overall_status = 'degraded'
                    
            except ImportError:
                health_results['consolidated_cache'] = {
                    'status': 'unavailable',
                    'error': 'Consolidated cache not available'
                }
            except Exception as e:
                health_results['consolidated_cache'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
        
        # Add overall status
        health_results['overall_status'] = overall_status
        health_results['timestamp'] = datetime.now().isoformat()
        
        # Output results
        if output_format == 'json':
            self.stdout.write(json.dumps(health_results, indent=2, default=str))
        else:
            self._format_health_output(health_results, verbose)
    
    def _clear_cache(self, cache_type, verbose):
        """Clear specified cache types."""
        self.stdout.write("🗑️  Cache Clearing Operation")
        self.stdout.write("=" * 50)
        
        cleared_count = 0
        
        if cache_type in ['all', 'django']:
            try:
                cache.clear()
                cleared_count += 1
                self.stdout.write(self.style.SUCCESS("✅ Django cache cleared"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Django cache clear failed: {e}"))
        
        if cache_type in ['all', 'unified', 'search']:
            try:
                from restaurants.signals import invalidate_all_search_cache
                invalidate_all_search_cache()
                cleared_count += 1
                self.stdout.write(self.style.SUCCESS("✅ Unified search cache cleared"))
            except ImportError:
                self.stdout.write(self.style.WARNING("⚠️  Search cache not available"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Search cache clear failed: {e}"))
        
        if cache_type in ['all', 'restaurant']:
            try:
                from restaurants.signals import invalidate_restaurant_view_cache
                invalidate_restaurant_view_cache()
                cleared_count += 1
                self.stdout.write(self.style.SUCCESS("✅ Restaurant view cache cleared"))
            except ImportError:
                self.stdout.write(self.style.WARNING("⚠️  Restaurant cache not available"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Restaurant cache clear failed: {e}"))
        
        self.stdout.write(f"\n🎯 Cleared {cleared_count} cache layers")
    
    def _warm_cache(self, cache_type, verbose):
        """Warm up cache with frequently accessed data."""
        self.stdout.write("🔥 Cache Warming Operation")
        self.stdout.write("=" * 50)
        
        warmed_count = 0
        
        if cache_type in ['all', 'restaurant']:
            try:
                # Warm up featured restaurants
                from restaurants.models import Restaurant
                from django.core.cache import cache
                
                featured_restaurants = Restaurant.objects.filter(
                    is_active=True, is_featured=True
                ).select_related().prefetch_related(
                    'images', 'chefs', 'menu_sections'
                )[:10]
                
                cache.set('featured_restaurants_data', list(featured_restaurants), 1800)
                warmed_count += 1
                
                # Warm up Michelin restaurants
                michelin_restaurants = Restaurant.objects.filter(
                    is_active=True, michelin_stars__gt=0
                ).select_related().prefetch_related(
                    'images', 'chefs', 'menu_sections'
                )[:20]
                
                cache.set('michelin_starred_restaurants_data', list(michelin_restaurants), 1800)
                warmed_count += 1
                
                self.stdout.write(self.style.SUCCESS("✅ Restaurant cache warmed"))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Restaurant cache warming failed: {e}"))
        
        self.stdout.write(f"\n🎯 Warmed {warmed_count} cache entries")
    
    def _analyze_cache_performance(self, cache_type, verbose, output_format):
        """Analyze cache performance and provide recommendations."""
        self.stdout.write("🔍 Cache Performance Analysis")
        self.stdout.write("=" * 50)
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'performance_metrics': {},
            'recommendations': [],
            'optimization_opportunities': []
        }
        
        try:
            # Get cache statistics for analysis
            stats = {}
            
            if cache_type in ['all', 'unified']:
                from restaurants.cache_integration import get_django_cache
                django_cache_integration = get_django_cache()
                unified_stats = django_cache_integration.get_cache_stats()
                stats['unified'] = unified_stats
            
            if cache_type in ['all']:
                from restaurants.cache_strategy import get_consolidated_cache
                consolidated_cache = get_consolidated_cache()
                consolidated_stats = consolidated_cache.get_consolidated_stats()
                stats['consolidated'] = consolidated_stats
            
            # Analyze performance
            analysis = self._perform_cache_analysis(stats)
            
        except Exception as e:
            analysis['error'] = str(e)
        
        # Output results
        if output_format == 'json':
            self.stdout.write(json.dumps(analysis, indent=2, default=str))
        else:
            self._format_analysis_output(analysis, verbose)
    
    def _get_django_cache_stats(self):
        """Get Django cache statistics."""
        return {
            'backend': settings.CACHES['default']['BACKEND'],
            'location': settings.CACHES['default']['LOCATION'],
            'key_prefix': settings.CACHES['default'].get('KEY_PREFIX', ''),
            'timeout': settings.CACHES['default'].get('TIMEOUT', 3600),
            'status': 'configured'
        }
    
    def _format_stats_output(self, stats, verbose):
        """Format statistics output for text display."""
        for cache_name, cache_stats in stats.items():
            self.stdout.write(f"\n📋 {cache_name.upper()}")
            self.stdout.write("-" * 30)
            
            if 'error' in cache_stats:
                self.stdout.write(self.style.ERROR(f"❌ Error: {cache_stats['error']}"))
                continue
            
            # Display key metrics
            if 'performance' in cache_stats:
                perf = cache_stats['performance']
                hit_rate = perf.get('hit_rate_percentage', 0)
                
                if hit_rate >= 80:
                    hit_style = self.style.SUCCESS
                elif hit_rate >= 60:
                    hit_style = self.style.WARNING
                else:
                    hit_style = self.style.ERROR
                
                self.stdout.write(f"Hit Rate: {hit_style(f'{hit_rate}%')}")
                self.stdout.write(f"Total Requests: {perf.get('total_requests', 0)}")
                self.stdout.write(f"Cache Hits: {perf.get('cache_hits', 0)}")
                self.stdout.write(f"Cache Misses: {perf.get('cache_misses', 0)}")
                self.stdout.write(f"Cache Errors: {perf.get('cache_errors', 0)}")
            
            if verbose and 'primary_cache' in cache_stats:
                primary = cache_stats['primary_cache']
                self.stdout.write(f"Memory Used: {primary.get('used_memory_human', 'Unknown')}")
                self.stdout.write(f"Connected Clients: {primary.get('connected_clients', 0)}")
    
    def _format_health_output(self, health_results, verbose):
        """Format health check output for text display."""
        overall_status = health_results.get('overall_status', 'unknown')
        
        if overall_status == 'healthy':
            status_style = self.style.SUCCESS
            status_icon = "✅"
        elif overall_status == 'degraded':
            status_style = self.style.WARNING
            status_icon = "⚠️"
        else:
            status_style = self.style.ERROR
            status_icon = "❌"
        
        self.stdout.write(f"\n{status_icon} Overall Status: {status_style(overall_status.upper())}")
        
        for cache_name, cache_health in health_results.items():
            if cache_name in ['overall_status', 'timestamp']:
                continue
                
            self.stdout.write(f"\n📋 {cache_name.upper()}")
            
            if isinstance(cache_health, dict):
                status = cache_health.get('status', 'unknown')
                if status == 'healthy':
                    self.stdout.write(self.style.SUCCESS(f"✅ {status}"))
                elif status == 'degraded':
                    self.stdout.write(self.style.WARNING(f"⚠️  {status}"))
                else:
                    self.stdout.write(self.style.ERROR(f"❌ {status}"))
                
                if 'error' in cache_health:
                    self.stdout.write(f"   Error: {cache_health['error']}")
    
    def _format_analysis_output(self, analysis, verbose):
        """Format performance analysis output for text display."""
        if 'error' in analysis:
            self.stdout.write(self.style.ERROR(f"❌ Analysis failed: {analysis['error']}"))
            return
        
        # Show recommendations
        recommendations = analysis.get('recommendations', [])
        if recommendations:
            self.stdout.write("\n💡 RECOMMENDATIONS:")
            for i, rec in enumerate(recommendations, 1):
                self.stdout.write(f"  {i}. {rec}")
        
        # Show optimization opportunities
        opportunities = analysis.get('optimization_opportunities', [])
        if opportunities:
            self.stdout.write("\n🚀 OPTIMIZATION OPPORTUNITIES:")
            for i, opp in enumerate(opportunities, 1):
                self.stdout.write(f"  {i}. {opp}")
    
    def _perform_cache_analysis(self, stats):
        """Perform detailed cache performance analysis."""
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'performance_metrics': {},
            'recommendations': [],
            'optimization_opportunities': []
        }
        
        # Analyze unified cache performance
        if 'unified' in stats:
            unified = stats['unified']
            redis_stats = unified.get('redis_cache', {})
            performance = redis_stats.get('performance', {})
            
            hit_rate = performance.get('hit_rate_percentage', 0)
            analysis['performance_metrics']['unified_hit_rate'] = hit_rate
            
            if hit_rate < 70:
                analysis['recommendations'].append(
                    f"Unified cache hit rate is {hit_rate}% - consider increasing TTL or improving cache keys"
                )
            
            cache_errors = performance.get('cache_errors', 0)
            if cache_errors > 10:
                analysis['recommendations'].append(
                    f"High cache error count ({cache_errors}) - investigate Redis connection issues"
                )
        
        # Analyze consolidated cache performance
        if 'consolidated' in stats:
            consolidated = stats['consolidated']
            consolidated_metrics = consolidated.get('consolidated_metrics', {})
            
            total_requests = consolidated_metrics.get('total_requests', 0)
            if total_requests > 0:
                consolidated_hit_rate = consolidated_metrics.get('hit_rate_percentage', 0)
                analysis['performance_metrics']['consolidated_hit_rate'] = consolidated_hit_rate
                
                if consolidated_hit_rate < 60:
                    analysis['recommendations'].append(
                        "Consolidated cache strategy needs optimization - low hit rate across layers"
                    )
        
        # Add optimization opportunities
        analysis['optimization_opportunities'].extend([
            "Consider implementing cache warming for frequently accessed data",
            "Review cache key strategies for better hit rates",
            "Implement cache monitoring and alerting",
            "Consider cache compression for large objects"
        ])
        
        return analysis