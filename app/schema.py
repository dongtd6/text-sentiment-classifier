from pydantic import BaseModel, Field
from typing import List
# --- Định nghĩa Schema Pydantic cho Request và Response ---
# Pydantic giúp FastAPI tự động xác thực dữ liệu và tạo tài liệu API.
class PredictRequest(BaseModel):
    comment: str = Field(..., example="Sản phẩm này rất tốt!")

class PredictResponse(BaseModel):
    original_comment: str = Field(..., example="Sản phẩm này rất tốt!")
    predicted_sentiment: str = Field(..., example="POS")

class BatchPredictRequest(BaseModel):
    comments: List[str] = Field(..., example=[
"Sản phẩm tốt.",
"Hàng giao chậm.",
"Tôi không hài lòng với chất lượng.",
"Dịch vụ khách hàng tuyệt vời!",
"Sản phẩm không đúng mô tả.",
"Tôi sẽ không mua lại.",
"Rất hài lòng với sản phẩm này.",
"Công nghệ hơi lạ, ko biết có bền ko.",
"Chất lượng sản phẩm rất tốt, tôi sẽ giới thiệu cho bạn bè.",
"Giá cả hợp lý, dịch vụ tốt.",  
"Không hài lòng với sản phẩm, chất lượng kém.",
"Đóng gói sản phẩm rất cẩn thận.",
"Thời gian giao hàng nhanh chóng, sản phẩm đúng như mô tả.",
"Chất lượng sản phẩm vượt quá mong đợi.",
"Tạm ổn",
"Rất thất vọng với sản phẩm này, không như quảng cáo.",
"Chất lượng sản phẩm không tốt, tôi sẽ không mua nữa.",
"Rất ấn tượng với dịch vụ khách hàng, họ rất nhiệt tình.",
"Chất lượng sản phẩm rất tốt, tôi sẽ mua lại.",
"Bình thường",
"Không hài lòng với thời gian giao hàng, quá chậm.",
"Rất hài lòng với sản phẩm, đúng như mô tả.",
"Đóng gói sản phẩm rất đẹp và chắc chắn.",
"Chất lượng sản phẩm vượt quá mong đợi, tôi rất hài lòng.",
"Chất lượng sản phẩm không tốt, tôi sẽ không mua nữa.",
"Chất lượng kém, không đáng tiền.",
"Giao hàng nhanh chóng, sản phẩm ổn.",
"Với giá này thì sản phẩm tạm ổn chưa đc gọi là đẹp lắm.",
"Sp tạm được, hơi rộng so vs mình."
])

class BatchPredictResponse(BaseModel):
    predictions: List[PredictResponse]

class HealthCheckResponse(BaseModel):
    status: str = Field(..., example="ok")
    models_loaded: bool = Field(..., example=True)
