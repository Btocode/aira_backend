#!/usr/bin/env python3
"""
Load sample data for development and testing.
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta
from uuid import uuid4

# Add app to path
sys.path.append(str(Path(__file__).parent.parent))

from app.db.database import SessionLocal
from app.db.models import (
    User, Paper, UserPaper, KnowledgeEntry, Citation,
    SubscriptionTier, ProcessingStatus, PaperSource, ReadingStatus, EntryType
)
from app.core.security import SecurityUtils
from app.core.app_logging import setup_logging, paper_logger


class SampleDataLoader:
    """Load sample data for development."""

    def __init__(self):
        self.db = SessionLocal()
        self.users = []
        self.papers = []

    def load_all(self):
        """Load all sample data."""
        paper_logger.info("🚀 Loading sample data...")

        try:
            self.create_sample_users()
            self.create_sample_papers()
            self.create_user_paper_relationships()
            self.create_sample_knowledge_entries()
            self.create_sample_citations()

            self.db.commit()
            paper_logger.info("✅ Sample data loaded successfully!")

        except Exception as e:
            paper_logger.error(f"❌ Failed to load sample data: {e}")
            self.db.rollback()
            raise
        finally:
            self.db.close()

    def create_sample_users(self):
        """Create sample users."""
        paper_logger.info("Creating sample users...")

        users_data = [
            {
                "email": "researcher@university.edu",
                "password": "researcher123",
                "full_name": "Dr. Sarah Chen",
                "subscription_tier": SubscriptionTier.RESEARCHER,
                "research_interests": ["machine learning", "natural language processing", "computer vision"],
                "is_verified": True
            },
            {
                "email": "student@gradschool.edu",
                "password": "student123",
                "full_name": "Alex Johnson",
                "subscription_tier": SubscriptionTier.FREE,
                "research_interests": ["artificial intelligence", "robotics"],
                "is_verified": True
            },
            {
                "email": "professor@institute.edu",
                "password": "professor123",
                "full_name": "Prof. Michael Rodriguez",
                "subscription_tier": SubscriptionTier.INSTITUTION,
                "research_interests": ["deep learning", "neural networks", "AI ethics"],
                "is_verified": True
            },
            {
                "email": "postdoc@lab.edu",
                "password": "postdoc123",
                "full_name": "Dr. Emily Zhang",
                "subscription_tier": SubscriptionTier.RESEARCHER,
                "research_interests": ["computer science", "data science", "machine learning"],
                "is_verified": True
            }
        ]

        for user_data in users_data:
            password = user_data.pop("password")
            user = User(
                **user_data,
                hashed_password=SecurityUtils.get_password_hash(password),
                created_at=datetime.utcnow() - timedelta(days=30),
                last_login_at=datetime.utcnow() - timedelta(days=1)
            )
            self.db.add(user)
            self.users.append(user)

        paper_logger.info(f"Created {len(users_data)} sample users")

    def create_sample_papers(self):
        """Create sample papers."""
        paper_logger.info("Creating sample papers...")

        papers_data = [
            {
                "title": "Attention Is All You Need",
                "authors": [
                    {"name": "Ashish Vaswani", "affiliation": "Google Brain"},
                    {"name": "Noam Shazeer", "affiliation": "Google Brain"},
                    {"name": "Niki Parmar", "affiliation": "Google Research"}
                ],
                "abstract": "The dominant sequence transduction models are based on complex recurrent or convolutional neural networks that include an encoder and a decoder. The best performing models also connect the encoder and decoder through an attention mechanism. We propose a new simple network architecture, the Transformer, based solely on attention mechanisms, dispensing with recurrence and convolutions entirely.",
                "keywords": ["attention", "transformer", "neural networks", "sequence modeling"],
                "doi": "10.5555/3295222.3295349",
                "arxiv_id": "1706.03762",
                "url": "https://arxiv.org/abs/1706.03762",
                "pdf_url": "https://arxiv.org/pdf/1706.03762.pdf",
                "source": PaperSource.ARXIV,
                "publication_year": 2017,
                "journal": "Advances in Neural Information Processing Systems",
                "citation_count": 50000,
                "influence_score": 0.95,
                "processing_status": ProcessingStatus.COMPLETED,
                "summary": {
                    "research_question": "Can we build sequence transduction models using only attention mechanisms?",
                    "methodology": "Novel Transformer architecture with multi-head self-attention",
                    "key_findings": [
                        "Transformers outperform RNNs and CNNs on translation tasks",
                        "Self-attention provides better parallelization",
                        "Multi-head attention captures different representation subspaces"
                    ],
                    "limitations": ["Requires large amounts of training data", "Computational complexity"],
                    "significance": "Revolutionary architecture that became foundation for modern NLP",
                    "future_work": ["Apply to other domains", "Improve efficiency"],
                    "confidence_score": 0.95
                },
                "key_insights": [
                    {
                        "insight": "Self-attention mechanism can replace recurrence entirely",
                        "relevance_score": 0.9,
                        "section": "Architecture"
                    },
                    {
                        "insight": "Multi-head attention allows model to attend to different positions",
                        "relevance_score": 0.85,
                        "section": "Model"
                    }
                ]
            },
            {
                "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "authors": [
                    {"name": "Jacob Devlin", "affiliation": "Google AI"},
                    {"name": "Ming-Wei Chang", "affiliation": "Google AI"},
                    {"name": "Kenton Lee", "affiliation": "Google AI"}
                ],
                "abstract": "We introduce a new language representation model called BERT, which stands for Bidirectional Encoder Representations from Transformers. Unlike recent language representation models, BERT is designed to pre-train deep bidirectional representations from unlabeled text by jointly conditioning on both left and right context in all layers.",
                "keywords": ["BERT", "bidirectional", "transformers", "language model", "pre-training"],
                "doi": "10.18653/v1/N19-1423",
                "arxiv_id": "1810.04805",
                "url": "https://arxiv.org/abs/1810.04805",
                "pdf_url": "https://arxiv.org/pdf/1810.04805.pdf",
                "source": PaperSource.ARXIV,
                "publication_year": 2019,
                "journal": "NAACL-HLT",
                "citation_count": 40000,
                "influence_score": 0.92,
                "processing_status": ProcessingStatus.COMPLETED,
                "summary": {
                    "research_question": "How can we pre-train bidirectional representations for language understanding?",
                    "methodology": "Masked language model with next sentence prediction",
                    "key_findings": [
                        "Bidirectional training significantly improves performance",
                        "Pre-training + fine-tuning paradigm is highly effective",
                        "BERT achieves state-of-the-art on 11 NLP tasks"
                    ],
                    "limitations": ["Computational cost", "Model size"],
                    "significance": "Established pre-training paradigm for NLP",
                    "future_work": ["Model compression", "Domain adaptation"],
                    "confidence_score": 0.92
                }
            },
            {
                "title": "GPT-3: Language Models are Few-Shot Learners",
                "authors": [
                    {"name": "Tom B. Brown", "affiliation": "OpenAI"},
                    {"name": "Benjamin Mann", "affiliation": "OpenAI"},
                    {"name": "Nick Ryder", "affiliation": "OpenAI"}
                ],
                "abstract": "Recent work has demonstrated substantial gains on many NLP tasks and benchmarks by pre-training on a large corpus of text followed by fine-tuning on a specific task. While typically task-agnostic in architecture, this method still requires task-specific fine-tuning datasets of thousands or tens of thousands of examples.",
                "keywords": ["GPT-3", "language model", "few-shot learning", "in-context learning"],
                "doi": "10.5555/3495724.3496268",
                "arxiv_id": "2005.14165",
                "url": "https://arxiv.org/abs/2005.14165",
                "pdf_url": "https://arxiv.org/pdf/2005.14165.pdf",
                "source": PaperSource.ARXIV,
                "publication_year": 2020,
                "journal": "Advances in Neural Information Processing Systems",
                "citation_count": 25000,
                "influence_score": 0.88,
                "processing_status": ProcessingStatus.COMPLETED
            },
            {
                "title": "ResNet: Deep Residual Learning for Image Recognition",
                "authors": [
                    {"name": "Kaiming He", "affiliation": "Microsoft Research"},
                    {"name": "Xiangyu Zhang", "affiliation": "Microsoft Research"},
                    {"name": "Shaoqing Ren", "affiliation": "Microsoft Research"}
                ],
                "abstract": "Deeper neural networks are more difficult to train. We present a residual learning framework to ease the training of networks that are substantially deeper than those used previously. We explicitly reformulate the layers as learning residual functions with reference to the layer inputs, rather than learning unreferenced functions.",
                "keywords": ["ResNet", "residual learning", "deep networks", "computer vision"],
                "doi": "10.1109/CVPR.2016.90",
                "url": "https://arxiv.org/abs/1512.03385",
                "pdf_url": "https://arxiv.org/pdf/1512.03385.pdf",
                "source": PaperSource.ARXIV,
                "publication_year": 2016,
                "journal": "IEEE Conference on Computer Vision and Pattern Recognition",
                "citation_count": 60000,
                "influence_score": 0.94,
                "processing_status": ProcessingStatus.COMPLETED
            },
            {
                "title": "Generative Adversarial Networks",
                "authors": [
                    {"name": "Ian J. Goodfellow", "affiliation": "Université de Montréal"},
                    {"name": "Jean Pouget-Abadie", "affiliation": "Université de Montréal"},
                    {"name": "Mehdi Mirza", "affiliation": "Université de Montréal"}
                ],
                "abstract": "We propose a new framework for estimating generative models via an adversarial process, in which we simultaneously train two models: a generative model G that captures the data distribution, and a discriminative model D that estimates the probability that a sample came from the training data rather than G.",
                "keywords": ["GAN", "generative models", "adversarial training", "deep learning"],
                "doi": "10.5555/2969033.2969125",
                "arxiv_id": "1406.2661",
                "url": "https://arxiv.org/abs/1406.2661",
                "pdf_url": "https://arxiv.org/pdf/1406.2661.pdf",
                "source": PaperSource.ARXIV,
                "publication_year": 2014,
                "journal": "Advances in Neural Information Processing Systems",
                "citation_count": 35000,
                "influence_score": 0.90,
                "processing_status": ProcessingStatus.COMPLETED
            }
        ]

        for paper_data in papers_data:
            paper = Paper(
                **paper_data,
                created_at=datetime.utcnow() - timedelta(days=20),
                processed_at=datetime.utcnow() - timedelta(days=19)
            )
            self.db.add(paper)
            self.papers.append(paper)

        paper_logger.info(f"Created {len(papers_data)} sample papers")

    def create_user_paper_relationships(self):
        """Create user-paper relationships."""
        paper_logger.info("Creating user-paper relationships...")

        relationships = []

        # Each user has different papers with different statuses
        for i, user in enumerate(self.users):
            # Each user gets 3-4 papers
            user_papers = self.papers[i:i+4] if i+4 <= len(self.papers) else self.papers[i:]

            for j, paper in enumerate(user_papers):
                status = [ReadingStatus.COMPLETED, ReadingStatus.READING, ReadingStatus.SAVED][j % 3]

                user_paper = UserPaper(
                    user_id=user.id,
                    paper_id=paper.id,
                    status=status,
                    reading_progress=90 if status == ReadingStatus.COMPLETED else (50 if status == ReadingStatus.READING else 0),
                    time_spent=3600 if status == ReadingStatus.COMPLETED else (1800 if status == ReadingStatus.READING else 0),
                    rating=5 if status == ReadingStatus.COMPLETED else None,
                    tags=["important", "research"] if j == 0 else ["interesting"],
                    notes=f"Great paper on {paper.title[:20]}..." if status == ReadingStatus.COMPLETED else None,
                    created_at=datetime.utcnow() - timedelta(days=15),
                    last_accessed_at=datetime.utcnow() - timedelta(days=1)
                )
                self.db.add(user_paper)
                relationships.append(user_paper)

        paper_logger.info(f"Created {len(relationships)} user-paper relationships")

    def create_sample_knowledge_entries(self):
        """Create sample knowledge entries."""
        paper_logger.info("Creating sample knowledge entries...")

        entries_data = [
            {
                "user": self.users[0],
                "paper": self.papers[0],
                "title": "Key Insights from Transformer Architecture",
                "content": "The Transformer architecture revolutionized NLP by using self-attention mechanisms instead of recurrence. Key innovations include: 1) Multi-head attention for capturing different types of relationships, 2) Positional encoding for sequence information, 3) Layer normalization and residual connections for training stability.",
                "entry_type": EntryType.SUMMARY,
                "tags": ["transformers", "attention", "architecture"],
                "section_reference": "Model Architecture"
            },
            {
                "user": self.users[0],
                "paper": self.papers[1],
                "title": "BERT Pre-training Strategy",
                "content": "BERT's bidirectional training is achieved through masked language modeling - randomly masking tokens and predicting them using context from both directions. This is combined with next sentence prediction for understanding sentence relationships.",
                "entry_type": EntryType.NOTE,
                "tags": ["BERT", "pre-training", "bidirectional"],
                "section_reference": "Pre-training Tasks"
            },
            {
                "user": self.users[1],
                "paper": self.papers[2],
                "title": "GPT-3 Few-Shot Learning Capabilities",
                "content": "GPT-3 demonstrates remarkable few-shot learning abilities without gradient updates. By providing examples in the prompt, it can perform tasks it wasn't explicitly trained for. This suggests emergent abilities from scale.",
                "entry_type": EntryType.INSIGHT,
                "tags": ["GPT-3", "few-shot", "emergent abilities"],
                "section_reference": "Results"
            },
            {
                "user": self.users[2],
                "paper": self.papers[3],
                "title": "Residual Connections Solve Degradation Problem",
                "content": "The key insight of ResNet is that residual connections allow gradients to flow directly through the network, solving the degradation problem in very deep networks. The residual function F(x) = H(x) - x is easier to optimize than the original mapping H(x).",
                "entry_type": EntryType.SUMMARY,
                "tags": ["ResNet", "residual", "deep learning"],
                "section_reference": "Deep Residual Learning"
            },
            {
                "user": self.users[0],
                "paper": None,
                "title": "Research Question: Scaling Laws in Language Models",
                "content": "How do language model capabilities scale with model size, dataset size, and compute? Recent papers suggest power-law relationships, but what are the theoretical foundations and practical implications for research directions?",
                "entry_type": EntryType.QUESTION,
                "tags": ["scaling", "language models", "research question"]
            }
        ]

        for entry_data in entries_data:
            entry = KnowledgeEntry(
                user_id=entry_data["user"].id,
                paper_id=entry_data["paper"].id if entry_data["paper"] else None,
                title=entry_data["title"],
                content=entry_data["content"],
                entry_type=entry_data["entry_type"],
                tags=entry_data["tags"],
                section_reference=entry_data.get("section_reference"),
                created_at=datetime.utcnow() - timedelta(days=10),
                updated_at=datetime.utcnow() - timedelta(days=5)
            )
            self.db.add(entry)

        paper_logger.info(f"Created {len(entries_data)} knowledge entries")

    def create_sample_citations(self):
        """Create sample citations between papers."""
        paper_logger.info("Creating sample citations...")

        # Create realistic citation relationships
        citations_data = [
            {
                "citing": self.papers[1],  # BERT
                "cited": self.papers[0],   # Transformer
                "context": "Building on the Transformer architecture (Vaswani et al., 2017), we propose BERT...",
                "strength": 0.9
            },
            {
                "citing": self.papers[2],  # GPT-3
                "cited": self.papers[0],   # Transformer
                "context": "We use the Transformer decoder architecture as the base for our language model...",
                "strength": 0.8
            },
            {
                "citing": self.papers[2],  # GPT-3
                "cited": self.papers[1],   # BERT
                "context": "Unlike BERT which uses bidirectional attention, our approach uses causal attention...",
                "strength": 0.7
            }
        ]

        for citation_data in citations_data:
            citation = Citation(
                citing_paper_id=citation_data["citing"].id,
                cited_paper_id=citation_data["cited"].id,
                context=citation_data["context"],
                strength=citation_data["strength"],
                created_at=datetime.utcnow() - timedelta(days=8)
            )
            self.db.add(citation)

        paper_logger.info(f"Created {len(citations_data)} citations")


def main():
    """Main function to load sample data."""
    setup_logging()

    loader = SampleDataLoader()
    loader.load_all()

    print("\n🎉 Sample data loaded successfully!")
    print("\nSample Users:")
    print("- researcher@university.edu (password: researcher123)")
    print("- student@gradschool.edu (password: student123)")
    print("- professor@institute.edu (password: professor123)")
    print("- postdoc@lab.edu (password: postdoc123)")
    print("\nYou can now:")
    print("1. Login with any of these accounts")
    print("2. Explore the sample papers and knowledge entries")
    print("3. Test the API endpoints")
    print("4. View the citation network")


if __name__ == "__main__":
    main()