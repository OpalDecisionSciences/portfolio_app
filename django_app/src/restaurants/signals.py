"""
Signals for the restaurants app.
"""
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Avg
from .models import Restaurant, RestaurantReview


@receiver(post_save, sender=RestaurantReview)
def update_restaurant_rating(sender, instance, created, **kwargs):
    """
    Update restaurant rating when a review is added or updated.
    """
    if instance.is_approved:
        restaurant = instance.restaurant
        
        # Calculate new average rating
        avg_rating = restaurant.reviews.filter(is_approved=True).aggregate(
            Avg('rating')
        )['rating__avg']
        
        # Update restaurant rating and review count
        restaurant.rating = avg_rating
        restaurant.review_count = restaurant.reviews.filter(is_approved=True).count()
        restaurant.save(update_fields=['rating', 'review_count'])


@receiver(post_delete, sender=RestaurantReview)
def update_restaurant_rating_on_delete(sender, instance, **kwargs):
    """
    Update restaurant rating when a review is deleted.
    """
    if instance.is_approved:
        restaurant = instance.restaurant
        
        # Calculate new average rating
        avg_rating = restaurant.reviews.filter(is_approved=True).aggregate(
            Avg('rating')
        )['rating__avg']
        
        # Update restaurant rating and review count
        restaurant.rating = avg_rating
        restaurant.review_count = restaurant.reviews.filter(is_approved=True).count()
        restaurant.save(update_fields=['rating', 'review_count'])