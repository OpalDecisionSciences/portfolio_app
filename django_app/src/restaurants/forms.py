"""
Forms for the restaurants app.
"""
from django import forms
from django.core.exceptions import ValidationError
from .models import RestaurantReview, Restaurant


class RestaurantReviewForm(forms.ModelForm):
    """Form for adding restaurant reviews."""
    
    class Meta:
        model = RestaurantReview
        fields = ['title', 'content', 'rating', 'visit_date']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Review title'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Share your experience at this restaurant...'
            }),
            'rating': forms.Select(attrs={
                'class': 'form-control'
            }, choices=[(i, f'{i} Star{"s" if i > 1 else ""}') for i in range(1, 6)]),
            'visit_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
    
    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content) < 50:
            raise ValidationError("Review must be at least 50 characters long.")
        return content
    
    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if not (1 <= rating <= 5):
            raise ValidationError("Rating must be between 1 and 5.")
        return rating


class RestaurantSearchForm(forms.Form):
    """Form for restaurant search and filtering."""
    
    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search restaurants, cities, or cuisines...'
        })
    )
    
    country = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    city = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    cuisine_type = forms.ChoiceField(
        choices=[],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    michelin_stars = forms.ChoiceField(
        choices=[
            ('', 'Any'),
            ('0', 'No Stars'),
            ('1', '1 Star'),
            ('2', '2 Stars'),
            ('3', '3 Stars'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    price_range = forms.ChoiceField(
        choices=[
            ('', 'Any Price'),
            ('$', 'Budget ($)'),
            ('$$', 'Moderate ($$)'),
            ('$$$', 'Expensive ($$$)'),
            ('$$$$', 'Very Expensive ($$$$)'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    sort_by = forms.ChoiceField(
        choices=[
            ('name', 'Name'),
            ('rating', 'Rating'),
            ('stars', 'Michelin Stars'),
            ('city', 'City'),
        ],
        required=False,
        widget=forms.Select(attrs={
            'class': 'form-control'
        })
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Dynamically populate choices from database
        self.fields['country'].choices = [('', 'All Countries')] + [
            (country, country) for country in 
            Restaurant.objects.filter(is_active=True).values_list('country', flat=True).distinct().order_by('country')
        ]
        
        self.fields['city'].choices = [('', 'All Cities')] + [
            (city, city) for city in 
            Restaurant.objects.filter(is_active=True).values_list('city', flat=True).distinct().order_by('city')
        ]
        
        self.fields['cuisine_type'].choices = [('', 'All Cuisines')] + [
            (cuisine, cuisine) for cuisine in 
            Restaurant.objects.filter(is_active=True).values_list('cuisine_type', flat=True).distinct().order_by('cuisine_type')
        ]


class RestaurantForm(forms.ModelForm):
    """Form for adding/editing restaurants."""
    
    class Meta:
        model = Restaurant
        fields = [
            'name', 'description', 'country', 'city', 'address',
            'latitude', 'longitude', 'phone', 'email', 'website',
            'michelin_stars', 'michelin_guide_year', 'cuisine_type',
            'price_range', 'atmosphere', 'seating_capacity',
            'has_private_dining', 'opening_hours', 'is_featured'
        ]
        
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Restaurant name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Restaurant description...'
            }),
            'country': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Country'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'City'
            }),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Full address'
            }),
            'latitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 'any',
                'placeholder': 'Latitude'
            }),
            'longitude': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': 'any',
                'placeholder': 'Longitude'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone number'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Email address'
            }),
            'website': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'Website URL'
            }),
            'michelin_stars': forms.Select(attrs={
                'class': 'form-control'
            }),
            'michelin_guide_year': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Year'
            }),
            'cuisine_type': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Cuisine type'
            }),
            'price_range': forms.Select(attrs={
                'class': 'form-control'
            }),
            'atmosphere': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Atmosphere description'
            }),
            'seating_capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Number of seats'
            }),
            'has_private_dining': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'opening_hours': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Opening hours...'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
    
    def clean_latitude(self):
        latitude = self.cleaned_data.get('latitude')
        if latitude is not None and not (-90 <= latitude <= 90):
            raise ValidationError("Latitude must be between -90 and 90.")
        return latitude
    
    def clean_longitude(self):
        longitude = self.cleaned_data.get('longitude')
        if longitude is not None and not (-180 <= longitude <= 180):
            raise ValidationError("Longitude must be between -180 and 180.")
        return longitude
    
    def clean_michelin_guide_year(self):
        year = self.cleaned_data.get('michelin_guide_year')
        if year is not None and year < 1900:
            raise ValidationError("Michelin Guide year must be 1900 or later.")
        return year