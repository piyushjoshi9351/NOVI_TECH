-- MySQL dump 10.13  Distrib 9.6.0, for macos15.7 (arm64)
--
-- Host: localhost    Database: novi_db
-- ------------------------------------------------------
-- Server version	9.4.0

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `university_matches`
--

DROP TABLE IF EXISTS `university_matches`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `university_matches` (
  `id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `university_id` int NOT NULL,
  `course` varchar(255) NOT NULL,
  `readiness` float NOT NULL,
  `strengths` json DEFAULT NULL,
  `improvements` json DEFAULT NULL,
  `next_steps` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`id`),
  KEY `ix_university_matches_university_id` (`university_id`),
  KEY `ix_university_matches_user_id` (`user_id`),
  CONSTRAINT `university_matches_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
  CONSTRAINT `university_matches_ibfk_2` FOREIGN KEY (`university_id`) REFERENCES `universities` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `university_matches`
--

LOCK TABLES `university_matches` WRITE;
/*!40000 ALTER TABLE `university_matches` DISABLE KEYS */;
INSERT INTO `university_matches` VALUES (1,1,1,'Computer Science',68,'[\"Entrepreneurial mindset\", \"AI & Robotics focus\", \"Programming background\"]','[\"Extracurricular depth\", \"Research experience\", \"Standardized test profile\"]','[\"Expand the gesture-control robot project into a published open-source tool or research paper\", \"Prepare for and achieve a top-percentile SAT/ACT score (1550+ / 35+)\", \"Lead or compete in high-impact national hackathons or robotics competitions\"]','2026-09-12 20:18:19'),(2,6,10,'Computer Science & Engineering',72,'[\"Academic performance\", \"Mathematics\", \"Coding\"]','[\"Research\", \"Leadership\", \"Extracurricular profile\"]','[\"Complete an AI research project\", \"Participate in a national coding competition\", \"Build and publish a technology project\"]','2026-09-12 23:44:58'),(3,6,1,'Computer Science',72,'[\"Academic performance\", \"Mathematics\", \"Coding\"]','[\"Research\", \"Leadership\", \"Extracurricular profile\"]','[\"Complete an AI research project\", \"Participate in a national coding competition\", \"Build and publish a technology project\"]','2026-09-13 00:42:25'),(4,6,14,'Computer Science',62,'[\"Mathematics & analytical skills\", \"Early Python programming experience\", \"Domain alignment with CS & AI\"]','[\"Competitive programming portfolio\", \"Advanced math coursework\", \"Extracurricular leadership & competitions\"]','[\"Start training for competitive programming contests like USACO or national math olympiads\", \"Advance Python skills by building a machine learning or cloud-hosted software project\", \"Take on leadership roles in the school coding club and participate in youth hackathons\"]','2026-09-13 16:41:03'),(5,6,2,'Electrical Engineering & Computer Science',72,'[\"Academic performance\", \"Mathematics\", \"Coding\"]','[\"Research\", \"Leadership\", \"Extracurricular profile\"]','[\"Complete an AI research project\", \"Participate in a national coding competition\", \"Build and publish a technology project\"]','2026-09-13 16:45:43'),(7,1,14,'Human-Computer Interaction',72,'[\"Academic performance\", \"Mathematics\", \"Coding\"]','[\"Research\", \"Leadership\", \"Extracurricular profile\"]','[\"Complete an AI research project\", \"Participate in a national coding competition\", \"Build and publish a technology project\"]','2026-09-17 21:21:13'),(8,6,1728,'Marketing',72,'[\"Academic performance\", \"Mathematics\", \"Coding\"]','[\"Research\", \"Leadership\", \"Extracurricular profile\"]','[\"Complete an AI research project\", \"Participate in a national coding competition\", \"Build and publish a technology project\"]','2026-09-18 11:17:47'),(9,6,1903,'Social Policy & Administration',54,'[\"Quantitative & analytical foundation\", \"Data analysis with Python\", \"Problem solving capabilities\"]','[\"Social policy exposure\", \"Civic leadership profile\", \"Policy research & writing\"]','[\"Conduct a data analysis project using Python on a public policy dataset\", \"Join the school debate club or Model UN to build foundational governance knowledge\", \"Write an article exploring how cloud technology and data can improve public administration\"]','2026-09-18 23:40:20'),(10,6,1229,'Engineering - Mechanical, Aeronautical & Manufacturing',62,'[\"Mathematics & analytical skills\", \"Python & data analysis foundation\", \"Problem solving\"]','[\"Physics & classical mechanics foundation\", \"Hands-on engineering projects\", \"Target course alignment\"]','[\"Strengthen Grade 9/10 CBSE Physics focus, specifically in mechanics and energy\", \"Build a robotics or mechatronics project combining Python programming with physical hardware\", \"Explore CAD software or simulation tools to bridge coding skills with mechanical engineering\"]','2026-09-20 16:20:21'),(11,6,1229,'Engineering - Mechanical, Aeronautical & Manufacturing',68,'[\"Mathematics\", \"Python programming\", \"Problem solving\"]','[\"Mechanical engineering focus\", \"Physics foundations\", \"Hands-on hardware projects\"]','[\"Explore mechanics and physics fundamentals alongside Grade 9 science and JEE preparation\", \"Build a combined hardware-software project using Arduino or Raspberry Pi to bridge coding with mechanical concepts\", \"Participate in a school robotics or science and engineering innovation competition\"]','2026-09-20 16:20:46'),(12,6,1229,'Engineering - Mechanical, Aeronautical & Manufacturing',64,'[\"Mathematics & analytical thinking\", \"Python programming\", \"Early project initiative\"]','[\"Mechanical engineering alignment\", \"Physics & mechanics foundation\", \"Domain-specific projects\"]','[\"Build a hardware-software project using Arduino or Raspberry Pi to connect coding skills with mechanical concepts\", \"Strengthen core Physics and Mechanics concepts as part of high school preparation\", \"Explore basic 3D CAD modeling or physics simulation tools to test interest in mechanical engineering\"]','2026-09-20 16:21:00');
/*!40000 ALTER TABLE `university_matches` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-09-24 23:31:08
